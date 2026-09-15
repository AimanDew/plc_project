import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_schema import get_config, set_config, get_latest_count
from erp_client import ERPClient, ERPClientError


# Demo fabrication: hardcoded rather than read from the BOM/Work Order.
#
# Known limitation: this closes the loop for ONE Work Order's worth of
# quantity (proven live against MFG-WO-2026-00004, qty=5) - it completes
# that Work Order's single Job Card and submits one Manufacture entry.
# It does NOT yet support repeated partial deliveries against one
# long-running Work Order (each delta would need its own Job Card
# time log against a still-open Job Card, which ERPNext's
# StockOverProductionError/process-loss checks did not accept cleanly
# in testing - see session notes). For continuous operation, either
# size the Work Order to each batch (as done here) or work out the
# correct partial-completion sequence against a single Job Card first.
WORK_ORDER = "MFG-WO-2026-00005"
FG_ITEM = "TRAINING-WIDGET"
FG_WAREHOUSE = "Finished Goods - W"
RM_ITEM = "WIDGET-BASE"
RM_WAREHOUSE = "Stores - W"
DEMO_RATE = 1.0

LAST_COUNT_KEY = "last_stock_entry_ok_count"
POLL_INTERVAL_SEC = 5.0


def ensure_negative_stock_allowed(client):

    settings = client.get_doc("Stock Settings", "Stock Settings")
    data = settings.get("data", settings) if isinstance(settings, dict) else settings

    if not data.get("allow_negative_stock"):
        client.update_doc("Stock Settings", "Stock Settings", {"allow_negative_stock": 1})
        print("Stock Settings: allow_negative_stock enabled")


def complete_job_card(client, qty):

    result = client.get_doc_list(
        "Job Card",
        filters=[["work_order", "=", WORK_ORDER], ["docstatus", "=", 0]],
        fields=["name", "operation"],
        limit=1
    )
    data = result.get("data", result) if isinstance(result, dict) else result
    if not data:
        return None

    jc_name = data[0]["name"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    client.update_doc("Job Card", jc_name, {
        "time_logs": [{
            "from_time": now, "to_time": now,
            "completed_qty": qty, "operation": data[0]["operation"]
        }]
    })
    client.submit_doc("Job Card", jc_name)
    return jc_name


def create_manufacture_stock_entry(client, qty):

    complete_job_card(client, qty)

    # ERPNext's own Work Order "Make Stock Entry" helper - builds the raw
    # material consumption row correctly (rate, warehouse) but, with
    # skip_transfer on, does not include the finished-good row itself.
    result = client.call_method(
        "erpnext.manufacturing.doctype.work_order.work_order.make_stock_entry",
        params={"work_order_id": WORK_ORDER, "purpose": "Manufacture", "qty": qty}
    )
    doc = result.get("message", result)
    doc["doctype"] = "Stock Entry"
    doc["process_loss_qty"] = 0
    doc["items"] = [i for i in doc.get("items", []) if not i.get("is_finished_item")]
    doc["items"].append({
        "item_code": FG_ITEM, "qty": qty, "t_warehouse": FG_WAREHOUSE,
        "is_finished_item": 1, "basic_rate": DEMO_RATE,
        "uom": "Unit", "stock_uom": "Unit", "conversion_factor": 1.0
    })

    saved = client.save_doc(doc)
    data = saved.get("message", saved)
    name = data["name"]

    client.submit_doc("Stock Entry", name)
    return name


def run_writeback(client=None, once=False):

    client = client or ERPClient()
    ensure_negative_stock_allowed(client)

    print(f"[{datetime.now().isoformat()}] Stock write-back starting")
    print(f"  Work Order: {WORK_ORDER}  ({RM_ITEM} -> {FG_ITEM})")

    while True:

        current = get_latest_count("OK Count")
        last = int(get_config(LAST_COUNT_KEY, 0))
        delta = current - last

        if delta > 0:
            try:
                name = create_manufacture_stock_entry(client, delta)
                set_config(LAST_COUNT_KEY, current)
                print(f"  + Stock Entry {name}: +{delta} {FG_ITEM}")
            except ERPClientError as e:
                print(f"  ! Stock Entry failed: {str(e)[:200]}")

        elif delta < 0:
            # counter rolled over/reset on the PLC side - resync baseline, no entry
            set_config(LAST_COUNT_KEY, current)

        if once:
            break

        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":

    once = "--once" in sys.argv
    run_writeback(once=once)
