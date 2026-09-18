import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "Omron_PLC_AI"))
sys.path.insert(0, PROJECT_ROOT)

from erp_client import ERPClient, ERPClientError
from erp_common import builders, plumbing


COMPANY = "w3ffwf"
FG_ITEM = "TRAINING-WIDGET"
RM_ITEM = "WIDGET-BASE"
SOURCE_WAREHOUSE = "Stores - W"
FG_WAREHOUSE = "Finished Goods - W"
OPERATION = "Assemble"

# WIDGET-BASE is drawn down to this level (Stock Reconciliation) before the
# two Work Orders below are created. 15 units of combined demand against 12
# available is the scarcity itself - neither WO can be fully served, so an
# allocation decision is forced instead of both lines just running.
SCARCE_QTY = 12
RM_VALUATION_RATE = 1.0

# Same finished item on both lines, deliberately - this is what makes a
# sequencing/dispatch decision real (distinct items per line would leave
# nothing to contend over). Cycle time is intentionally EQUAL across both
# lines this round (session decision, 2026-09-16) - it was a confound, not
# a genuine trade-off, when stock was abundant. What forces real judgment
# now is three axes stacked, deliberately pointing in different directions:
#   - stock scarcity (SCARCE_QTY): combined demand (15) exceeds supply (12)
#   - due date: WS-SIEMENS-001's WO is due sooner
#   - priority (custom_priority, Custom Field - see erp_schema/custom_fields/):
#     WS-MITSU-001's WO is the one flagged High despite the later due date
# No single axis picks a clear winner alone - that conflict is the point.
LINES = [
    {"workstation": "WS-SIEMENS-001", "time_in_mins": 0.05, "wo_qty": 8, "due_date": "2026-09-19", "priority": "Medium"},
    {"workstation": "WS-MITSU-001",   "time_in_mins": 0.05, "wo_qty": 7, "due_date": "2026-09-24", "priority": "High"},
]


def make_bom(client, workstation, time_in_mins):

    doc = builders.bom(
        item=FG_ITEM, company=COMPANY, component_item=RM_ITEM,
        operation=OPERATION, workstation=workstation, time_in_mins=time_in_mins,
    )
    name = plumbing.create_and_submit(client, "BOM", doc)
    print(f"  BOM {name} created + submitted ({workstation}, {time_in_mins} min/unit)")
    return name


def make_work_order(client, bom_no, workstation, time_in_mins, qty, due_date=None, priority=None):

    doc = builders.work_order(
        company=COMPANY, production_item=FG_ITEM, bom_no=bom_no, qty=qty,
        source_warehouse=SOURCE_WAREHOUSE, fg_warehouse=FG_WAREHOUSE,
        operation=OPERATION, workstation=workstation, time_in_mins=time_in_mins,
        expected_delivery_date=due_date, priority=priority,
    )
    name = plumbing.create_and_submit(client, "Work Order", doc)
    print(f"  Work Order {name} created + submitted (qty {qty} @ {workstation}, due {due_date}, priority {priority})")
    return name


def job_cards_for(client, wo_name):

    result = client.get_doc_list(
        "Job Card", filters=[["work_order", "=", wo_name]],
        fields=["name", "workstation", "operation", "status"], limit=10
    )
    return plumbing.unwrap(result)


def cleanup_previous_run(client):
    """Cancel any not-yet-started Work Order left over from an earlier run of
    this script, so re-running it produces one clean scenario instead of
    accumulating competing generations of demo data."""

    wos = plumbing.unwrap(client.get_doc_list(
        "Work Order",
        filters=[["production_item", "=", FG_ITEM], ["docstatus", "=", 1], ["status", "=", "Not Started"]],
        fields=["name"], limit=20,
    ))
    for wo in wos:
        name = wo["name"]
        jcs = plumbing.unwrap(client.get_doc_list(
            "Job Card", filters=[["work_order", "=", name], ["docstatus", "=", 0]],
            fields=["name"], limit=20,
        ))
        for jc in jcs:
            client.delete_doc("Job Card", jc["name"])
        client.cancel_doc("Work Order", name)
        print(f"  cleaned up stale Work Order {name}")


def fabricate_scarcity(client):
    """Draw WIDGET-BASE down to SCARCE_QTY via Stock Reconciliation - the
    legitimate ERPNext mechanism for setting a baseline count, not a direct
    Bin edit."""

    doc = builders.stock_reconciliation(
        company=COMPANY, item_code=RM_ITEM, warehouse=SOURCE_WAREHOUSE,
        qty=SCARCE_QTY, valuation_rate=RM_VALUATION_RATE,
    )
    name = plumbing.create_and_submit(client, "Stock Reconciliation", doc)
    print(f"  Stock Reconciliation {name}: {RM_ITEM} @ {SOURCE_WAREHOUSE} -> {SCARCE_QTY}")
    return name


if __name__ == "__main__":

    client = ERPClient()

    print("=== Cleanup: cancelling stale Work Orders from a prior run ===")
    cleanup_previous_run(client)

    print("=== Scarcity: drawing WIDGET-BASE down via Stock Reconciliation ===")
    fabricate_scarcity(client)

    for line in LINES:
        print(f"=== {line['workstation']} ===")
        bom_name = make_bom(client, line["workstation"], line["time_in_mins"])
        wo_name = make_work_order(
            client, bom_name, line["workstation"], line["time_in_mins"],
            line["wo_qty"], due_date=line["due_date"], priority=line["priority"],
        )
        cards = job_cards_for(client, wo_name)
        for jc in cards:
            print(f"    Job Card {jc['name']}: {jc['operation']} @ {jc['workstation']} [{jc['status']}]")
        if not cards:
            print("    ! no Job Card found - check Work Order submission")
