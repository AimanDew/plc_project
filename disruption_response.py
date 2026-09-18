import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "Omron_PLC_AI"))
sys.path.insert(0, HERE)

from dotenv import load_dotenv

import llm_providers
from erp_client import ERPClient, ERPClientError
from erp_common import plumbing

# Absolute path, not cwd-relative - so this loads .env regardless of which
# directory the script is invoked from (same reasoning as erp_client.py's
# CONFIG_PATH). Fill in .env from .env.example; .env itself is gitignored.
load_dotenv(os.path.join(HERE, ".env"))


# Layer 1 harness: everything except decide() is deterministic. The LLM only
# ever occupies the one slot where the inputs are genuinely incommensurable
# (stock vs due date vs supervisor priority) - see plc_project session
# history for why this specific shape, and why a smaller/enumerable input
# space would make the LLM call redundant instead of load-bearing.
FG_ITEM = "TRAINING-WIDGET"
RM_ITEM = "WIDGET-BASE"
SOURCE_WAREHOUSE = "Stores - W"


# ---------------------------------------------------------------------------
# Upstream - pure ERPNext reads. No decision is made here.
# ---------------------------------------------------------------------------

def detect_shortfall(client):
    """Return a shortfall dict if open Work Orders needing RM_ITEM collectively
    exceed what's on hand at SOURCE_WAREHOUSE, else None."""

    bin_docs = plumbing.unwrap(client.get_doc_list(
        "Bin", filters=[["item_code", "=", RM_ITEM], ["warehouse", "=", SOURCE_WAREHOUSE]],
        fields=["actual_qty"], limit=1,
    ))
    if not bin_docs:
        return None
    available = bin_docs[0]["actual_qty"]

    wo_names = plumbing.unwrap(client.get_doc_list(
        "Work Order",
        filters=[["production_item", "=", FG_ITEM], ["docstatus", "=", 1], ["status", "=", "Not Started"]],
        fields=["name"], limit=20,
    ))

    candidates = []
    for row in wo_names:
        wo = plumbing.unwrap(client.get_doc("Work Order", row["name"]))
        rm_rows = [i for i in wo.get("required_items", []) if i["item_code"] == RM_ITEM]
        if not rm_rows:
            continue
        candidates.append({
            "work_order": wo["name"],
            "qty_needed": rm_rows[0]["required_qty"],
            "due_date": wo.get("expected_delivery_date"),
            "priority": wo.get("custom_priority"),
        })

    total_needed = sum(c["qty_needed"] for c in candidates)
    if not candidates or total_needed <= available:
        return None

    return {
        "item": RM_ITEM,
        "warehouse": SOURCE_WAREHOUSE,
        "available_qty": available,
        "total_needed_qty": total_needed,
        "candidates": candidates,
    }


# ---------------------------------------------------------------------------
# Middle layer - the one LLM call. Output is constrained to naming one of the
# actual candidate Work Orders, or escalating - never free text, never an
# action outside that closed set.
# ---------------------------------------------------------------------------

def decide(shortfall):

    candidate_names = [c["work_order"] for c in shortfall["candidates"]]
    schema = {
        "type": "object",
        "properties": {
            "decision": {
                "type": "string",
                "enum": candidate_names + ["escalate_to_human"],
                "description": (
                    "The Work Order to favor for the scarce material, or "
                    "escalate_to_human if the facts below don't clearly favor one."
                ),
            },
            "rationale": {
                "type": "string",
                "description": (
                    "One or two sentences citing the specific facts weighed "
                    "(quantities, due dates, priority) - the audit record for "
                    "why the decision went this way."
                ),
            },
        },
        "required": ["decision", "rationale"],
        "additionalProperties": False,
    }

    prompt = (
        f"{shortfall['item']} is short at {shortfall['warehouse']}: "
        f"{shortfall['available_qty']} units available, "
        f"{shortfall['total_needed_qty']} needed across the Work Orders below - "
        f"not all of them can be fully supplied.\n\n"
        f"Decide which one to favor for the scarce material. Weigh quantity "
        f"needed, due date urgency, and priority against each other - none of "
        f"them alone determines the answer. If the facts genuinely don't "
        f"favor one, use escalate_to_human instead of guessing.\n\n"
        f"Candidates:\n{json.dumps(shortfall['candidates'], indent=2)}"
    )

    provider = os.environ.get("LLM_PROVIDER", "gemini")

    try:
        decision, label = llm_providers.call(provider, prompt, schema)
    except ValueError as e:
        # Parse/extraction failure (expected for providers that don't
        # enforce the schema server-side, e.g. Ollama Cloud) - escalate
        # rather than crash. A missing API key or unknown provider is a
        # RuntimeError instead and is left to propagate - that's a config
        # problem to fix, not a decision to escalate.
        return {
            "decision": "escalate_to_human",
            "rationale": f"could not get a parseable decision from {provider}: {e}",
            "provider_label": None,
        }

    decision["provider_label"] = label

    # Defense in depth: never trust a decision onto the dispatch table
    # without checking it landed in the closed set we actually asked for -
    # true for every provider, not just the ones that can't self-enforce it.
    valid_decisions = set(candidate_names) | {"escalate_to_human"}
    if decision.get("decision") not in valid_decisions or not decision.get("rationale"):
        return {
            "decision": "escalate_to_human",
            "rationale": f"{label} returned a decision outside the allowed set or missing rationale: {decision!r}",
            "provider_label": label,
        }

    return decision


# ---------------------------------------------------------------------------
# Downstream - deterministic again. Revalidate against live state right
# before writing, then dispatch through a fixed set of known branches.
# ---------------------------------------------------------------------------

def validate(client, shortfall, decision):
    """Re-check the decision against current ERPNext state - stock and Work
    Orders may have moved since `shortfall` was assembled."""

    if decision["decision"] == "escalate_to_human":
        return True

    valid_names = {c["work_order"] for c in shortfall["candidates"]}
    if decision["decision"] not in valid_names:
        return False

    fresh = detect_shortfall(client)
    if fresh is None:
        return False  # shortfall resolved since detection - nothing to act on
    return decision["decision"] in {c["work_order"] for c in fresh["candidates"]}


def _record(client, work_orders, content):
    # frappe.client.add_comment does not exist on this ERPNext version
    # (verified: 417 "module 'frappe.client' has no attribute 'add_comment'").
    # A Comment is a plain doctype - insert it directly instead.
    for wo_name in work_orders:
        client.insert_doc("Comment", {
            "doctype": "Comment",
            "comment_type": "Comment",
            "reference_doctype": "Work Order",
            "reference_name": wo_name,
            "content": content,
        })


def dispatch(client, shortfall, decision):

    work_orders = [c["work_order"] for c in shortfall["candidates"]]
    rationale = decision["rationale"]
    tag = f"disruption_response - {decision['provider_label']}" if decision.get("provider_label") else "disruption_response"

    if decision["decision"] == "escalate_to_human":
        _record(client, work_orders, f"[{tag}] Escalating - {rationale}")
        print(f"  escalated: {rationale}")
        return "escalate_to_human"

    favored = decision["decision"]
    _record(client, work_orders, (
        f"[{tag}] {shortfall['item']} shortfall "
        f"({shortfall['available_qty']} available vs {shortfall['total_needed_qty']} "
        f"needed): favoring {favored}. {rationale}"
    ))
    print(f"  favored {favored}: {rationale}")
    return favored


def run_once(client=None):

    client = client or ERPClient()
    shortfall = detect_shortfall(client)
    if shortfall is None:
        print("no shortfall detected")
        return None

    print(
        f"shortfall: {shortfall['item']} - {shortfall['available_qty']} available, "
        f"{shortfall['total_needed_qty']} needed across {len(shortfall['candidates'])} Work Orders"
    )

    decision = decide(shortfall)
    if not validate(client, shortfall, decision):
        print(f"  ! decision {decision['decision']!r} failed revalidation, escalating instead")
        decision = {
            "decision": "escalate_to_human",
            "rationale": (
                f"revalidation failed after the {decision.get('provider_label', 'LLM')} call - "
                f"state moved or decision was invalid"
            ),
            "provider_label": decision.get("provider_label"),
        }

    return dispatch(client, shortfall, decision)


if __name__ == "__main__":
    try:
        run_once()
    except RuntimeError as e:
        print(f"! {e}")
        sys.exit(1)
