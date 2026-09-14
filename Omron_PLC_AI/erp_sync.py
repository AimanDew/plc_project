import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_schema import (
    get_pending_outbox_events,
    mark_outbox_synced,
    mark_outbox_failed,
    get_outbox_stats
)
from erp_client import ERPClient, ERPClientError


POLL_INTERVAL_SEC = 5.0
BATCH_SIZE = 50
DEFAULT_WORKSTATION = "WS-OEE-001"

# machine_unit string -> ERPNext Workstation docname
MACHINE_UNIT_TO_WORKSTATION = {
    "OEE": DEFAULT_WORKSTATION
}

# active job card cache: workstation -> job card docname
# resolved from ERPNext: the open Job Card in 'Work In Progress' state
ACTIVE_JOB_CARD = {}


def resolve_workstation(client, machine_unit):

    ws = MACHINE_UNIT_TO_WORKSTATION.get(machine_unit)

    if ws is None:
        return None

    try:
        client.get_doc("Workstation", ws)
        return ws
    except ERPClientError:
        return None


def get_active_job_card(client, workstation):

    # the open (Work In Progress) Job Card for this workstation
    try:
        result = client.get_doc_list(
            "Job Card",
            filters=[["workstation", "=", workstation],
                     ["status", "=", "Work In Progress"]],
            limit=1
        )
        data = result["data"] if isinstance(result, dict) and "data" in result else result
        return data[0]["name"] if data else None
    except ERPClientError:
        return None


def map_event(event, workstation=None, job_card=None):

    event_type = event["event_type"]
    payload = event["payload"]

    common = {
        "event_type": event_type,
        "source_uuid": event["event_uuid"],
        "machine_unit": payload.get("machine_unit", "OEE"),
        "event_timestamp": payload.get("timestamp"),
        "state": payload.get("state"),
        "reason": payload.get("reason"),
        "payload": payload.get("raw_payload")
    }

    if workstation:
        common["workstation"] = workstation
    if job_card:
        common["job_card"] = job_card

    if event_type == "downtime_event":
        common["duration_sec"] = payload.get("duration_sec")
    elif event_type == "state_transition":
        common["duration_sec"] = payload.get("duration_sec")

    fields = {k: v for k, v in common.items() if v is not None}

    if not fields.get("event_timestamp"):
        fields["event_timestamp"] = datetime.now().isoformat()

    return fields


def process_event(client, event, workstation_cache):

    doc = client.find_by_source_uuid("Machine Event", event["event_uuid"])

    if doc is not None:
        return "already_synced"

    machine_unit = event["payload"].get("machine_unit", "OEE")

    if machine_unit not in workstation_cache:
        workstation_cache[machine_unit] = resolve_workstation(client, machine_unit)

    workstation = workstation_cache[machine_unit]

    # resolve active job card once per workstation per batch
    if workstation and workstation not in ACTIVE_JOB_CARD:
        ACTIVE_JOB_CARD[workstation] = get_active_job_card(client, workstation)

    fields = map_event(
        event,
        workstation=workstation,
        job_card=ACTIVE_JOB_CARD.get(workstation)
    )
    client.insert_doc("Machine Event", fields)
    return "created"


def run_sync(client=None, once=False):

    client = client or ERPClient()

    print(f"[{datetime.now().isoformat()}] ERP sync service starting")
    print(f"  Target: {client.base_url}")
    print(f"  Batch size: {BATCH_SIZE}")
    print()

    workstation_cache = {}

    while True:

        try:

            events = get_pending_outbox_events(BATCH_SIZE)

            if not events:

                if once:
                    stats = get_outbox_stats()
                    print(f"[{datetime.now().isoformat()}] Outbox drained: {stats}")
                    break

                time.sleep(POLL_INTERVAL_SEC)
                continue

            print(f"[{datetime.now().isoformat()}] Processing {len(events)} event(s)")

            for event in events:

                try:

                    result = process_event(client, event, workstation_cache)
                    mark_outbox_synced(event["id"])

                    if result == "created":
                        print(f"  + {event['event_type']} {event['event_uuid'][:8]}... -> ERP")
                    else:
                        print(f"  = {event['event_type']} {event['event_uuid'][:8]}... already in ERP")

                except ERPClientError as e:

                    mark_outbox_failed(event["id"], str(e)[:500])
                    print(f"  ! {event['event_type']} {event['event_uuid'][:8]}... failed: {str(e)[:120]}")

        except KeyboardInterrupt:

            print(f"\n[{datetime.now().isoformat()}] Stopped by user")
            break

        except Exception as e:

            print(f"[{datetime.now().isoformat()}] Unexpected error: {e}")
            time.sleep(POLL_INTERVAL_SEC)

        if once:
            stats = get_outbox_stats()
            print(f"[{datetime.now().isoformat()}] Batch done: {stats}")
            break

    stats = get_outbox_stats()
    print(f"Final outbox state: {stats}")


if __name__ == "__main__":

    once = "--once" in sys.argv
    run_sync(once=once)