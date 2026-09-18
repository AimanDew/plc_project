# AGENTS.md — plc_project (for OpenCode / other agentic CLIs)

This file briefs a coding agent with **no other context on this project** —
it doesn't share history with whatever produced `CLAUDE.md` or the rest of
this repo's state. This is durable, standing reference, not a task brief —
if you're looking for a specific assignment, the human giving you one will
say what it is; nothing here is "your job to go do."

## What this project is

Real PLC/OEE-monitoring + ERPNext integration codebase. A large amount of
the ERPNext-side data is **deliberately fabricated** for training/demo
purposes — not a real factory's numbers, not a real production incident.
Full detail (what's real hardware vs. fabricated data, across all three
lines) is in `CLAUDE.md` at this same repo root — read it before assuming
any number you see is a real signal worth investigating.

The local ERPNext instance is a from-scratch Docker deployment
(`frappe_docker/`) at `http://localhost:8080`, seeded for this project.
Negative stock is allowed; changing fabricated numbers to whatever a
scenario needs is expected practice here, not a data-integrity concern.

## `disruption_response.py`

A small LLM-in-the-loop agent at the project root: when a shared raw
material (`WIDGET-BASE`) is scarcer than the combined demand from open Work
Orders needing it, it calls an LLM to decide which Work Order to favor,
then writes that decision + rationale back to ERPNext as a `Comment` on
each Work Order involved. Read the file itself — it's short, and the three
sections (`detect_shortfall` / `decide` / `dispatch`) are self-explanatory.
The LLM call is routed through `llm_providers.py`, selected via the
`LLM_PROVIDER` env var (`.env`) — currently `gemini` or `ollama`.

The two Work Orders it currently contends over are `MFG-WO-2026-00008`
(Siemens line) and `MFG-WO-2026-00009` (Mitsubishi line), both drawing
`WIDGET-BASE` from `Stores - W`. Their exact stock level, due dates, and
`custom_priority` values change over time as the scenario is iterated on —
don't treat any specific numbers you see live as fixed; check the current
state rather than assume. `sessions/session-27.md` (sibling repo,
`ai_coding_assistant/sessions/`) has the full history of how this scenario
was built and a batch of trial runs against it, if you want the reasoning
behind a decision rather than just its current state.

## How to change the fabricated variables

**Stock** — via a `Stock Reconciliation` (the legitimate ERPNext mechanism
for setting a baseline count, not a direct `Bin` edit):

```python
import sys, os
sys.path.insert(0, "Omron_PLC_AI")
from erp_client import ERPClient
from erp_common import builders, plumbing

client = ERPClient()
doc = builders.stock_reconciliation(
    company="w3ffwf", item_code="WIDGET-BASE", warehouse="Stores - W",
    qty=<new_qty>, valuation_rate=1.0,
)
plumbing.create_and_submit(client, "Stock Reconciliation", doc)
```

(`fabricated_workstations/fabricate_lines.py`'s `fabricate_scarcity()` is
the same pattern already wired up.)

**Due dates** — a plain field update, no amend/cancel needed. Verified
writable post-submit (2026-09-16, tested live and reverted, not assumed):

```python
client.update_doc("Work Order", "MFG-WO-2026-00008", {"expected_delivery_date": "2026-09-22"})
```

**Priority** — same pattern, field is `custom_priority`
(`Low`/`Medium`/`High`/`Urgent`, a Custom Field, not native):

```python
client.update_doc("Work Order", "MFG-WO-2026-00009", {"custom_priority": "Low"})
```

## Acting as "Agent" instead of "Administrator"

Writes made through the default ERPNext credentials show up in the Desk UI
(Comment feed, timeline, "Created By") as `Administrator`. A dedicated
`Agent` user exists for work you'd rather attribute distinctly:

- `agent@plc-project.local` (full name "Agent"), with its own API key/secret
  in `Omron_PLC_AI/erp_config.agent.json` (gitignored - template at
  `erp_config.agent.sample.json`).
- `erp_client.py`'s `ERPClient()` picks up an alternate config via the
  `ERP_CONFIG_PATH` env var - no code changes needed:

  ```bash
  export ERP_CONFIG_PATH="$(pwd)/Omron_PLC_AI/erp_config.agent.json"
  ```
  ```powershell
  $env:ERP_CONFIG_PATH = "$PWD\Omron_PLC_AI\erp_config.agent.json"
  ```

**Verify this actually works before relying on it** - test with one
harmless read first:

```python
client.get_doc_list("Bin", filters=[["item_code", "=", "WIDGET-BASE"]], fields=["actual_qty"], limit=1)
```

If this 403s, **stop and tell the user** rather than falling back to the
default (Administrator) identity silently.

**A real gotcha, hit once already**: ERPNext role names don't reliably
predict doctype access. `Manufacturing Manager` looked like the obviously
correct role for `Work Order` and still 403'd - the actual `DocPerm` table
for that doctype only lists `Stock User` (read) and `Manufacturing User`
(read/write/create). If a plausible-sounding role doesn't work, check the
real permission table before guessing again:

```python
client.get_doc_list("DocPerm", filters=[["parent", "=", "Work Order"]], fields=["role", "read", "write", "create"], limit=50)
```

## Where to see `disruption_response.py`'s output

Run it with `python disruption_response.py` from the project root (it
loads `.env` itself). It prints the shortfall it detected (or "no shortfall
detected" if there isn't one) and the decision + rationale. The write it
made is visible in the Desk UI: either
`http://localhost:8080/app/work-order/<name>` (scroll to the
Comments/Activity feed), or `http://localhost:8080/app/comment` filtered by
`Reference Name`. Each comment is tagged with whichever provider actually
answered, e.g. `[disruption_response - Gemini]`.

## Standing boundaries

- Don't create new Work Orders, BOMs, or Workstations without being asked -
  ask which scenario is in scope first.
- Don't change `LLM_PROVIDER` without being asked.
- Don't grant yourself broader ERPNext roles or create additional users -
  if the `Agent` identity is insufficiently permissioned for a task, report
  that rather than working around it.
- Don't touch `git` - no commits, no staging. Report what changed;
  committing is a separate decision for the user to make.
- Session log files under the sibling `ai_coding_assistant/sessions/`
  folder are documentation only and are never git-committed from here or
  there - all git activity stays scoped to this repo.
