# plc_project — Project Instructions

Real PLC/OEE-monitoring + ERPNext integration codebase for an SHRDC-adjacent
internship, co-owned with a teammate (`AimanDew`) via direct pushes to `main`
(no branch protection, two people). The sibling repo `ai_coding_assistant`
(one directory up) holds the full narrative history of this project in
`sessions/session-N.md` — read the last several session files there for
context beyond what's captured here.

## A large amount of the data in this repo is deliberately fabricated

This matters enough to read before touching anything, especially if picking
this project up with no prior conversation context.

- **Omron/FINS line** (`Omron_PLC_AI/`) has real hardware integration — real
  PLC tag reads over FINS. The ERPNext-side business data it writes into
  (Items, BOM component ratios, Work Order quantities, valuation rates) is
  demo data, not a real factory's numbers. Stated explicitly by the user in
  project history: the data is a demo, precision doesn't matter.
- **Siemens/S7 line** (`AI_Assisstant_PLC/PLC_MCP_Server/`) also has real
  hardware integration — its tag map (`tag_map.json`) was hardware-verified
  against a live PLC via TIA Portal/Snap7. It has **zero ERPNext integration
  of its own**; a Workstation (`WS-SIEMENS-001`) and `PLC Tag` rows were
  fabricated into ERPNext later by reusing this real tag map, not from a live
  connection to ERPNext.
- **`WS-MITSU-001` / the Mitsubishi tag map**
  (`fabricated_workstations/mitsubishi_tag_map.json`) is **entirely
  fabricated** — no Mitsubishi PLC exists anywhere in this project. It exists
  purely to give a training/demo sequencing-dispatch scenario a third,
  structurally distinct vendor addressing scheme to reason about.
- **The local ERPNext instance itself** (`frappe_docker`, `localhost:8080`)
  is a from-scratch Docker deployment seeded for this project — not a real
  company's production system. Negative stock allowed, nominal valuation
  rates, arbitrary BOM ratios, and known loose data-integrity nits (e.g. one
  BOM with a mismatched `company` field that ERPNext doesn't enforce) are
  accepted as-is, not defects to silently "fix."
- **Stock levels and Work Order quantities across all three lines** (Omron,
  Siemens, Mitsubishi) are set to whatever a given training scenario needs,
  not driven by any real supply/demand signal. Don't infer a real shortage,
  disruption, or production event from a number in this instance without
  checking — it's far more likely someone (or an agent) set it that way for a
  demo than that it reflects something that "happened."

**Practical rule:** if a number here looks odd or interesting, the default
explanation is "this was authored for a demo," not a live data anomaly worth
investigating as if it were a real production incident — unless there's a
concrete, verified code-level bug behind it (check the code, don't assume the
data is broken).

## Git

Both collaborators push directly to `main`. Session/narrative log files under
the sibling `ai_coding_assistant/sessions/` folder are documentation only and
are never git-committed from here or there — all git activity stays scoped to
this repo (`plc_project`). Don't add Claude co-authorship trailers
(`Co-Authored-By`, `Claude-Session`) to commits or PRs in this repo.
