import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from erp_client import ERPClient, ERPClientError


TAG_MAP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tag_map.json")
DEFAULT_WORKSTATION = "WS-OEE-001"


def sync_tags(client, workstation=DEFAULT_WORKSTATION, dry_run=False):

    with open(TAG_MAP_PATH, "r", encoding="utf-8") as f:
        tag_map = json.load(f)

    created, updated, skipped = 0, 0, 0

    for tag_name, info in tag_map["tags"].items():

        existing = None
        try:
            result = client.get_doc_list(
                "PLC Tag",
                filters=[["tag_name", "=", tag_name]],
                limit=1
            )
            data = result["data"] if isinstance(result, dict) and "data" in result else result
            existing = data[0] if data else None
        except ERPClientError:
            existing = None

        fields = {
            "tag_name": tag_name,
            "fins_address": info["address"],
            "data_type": info["type"],
            "workstation": workstation if info.get("comment") or True else workstation,
            "comment": info.get("comment", ""),
            "active": 1
        }
        fields["workstation"] = workstation

        if existing:
            if dry_run:
                print(f"  [dry] would update {tag_name}")
                continue
            client.update_doc("PLC Tag", existing["name"], fields)
            updated += 1
        else:
            if dry_run:
                print(f"  [dry] would create {tag_name}")
                continue
            client.insert_doc("PLC Tag", fields)
            created += 1
            print(f"  + {tag_name} ({info['address']}) -> {workstation}")

    return created, updated, skipped


if __name__ == "__main__":

    client = ERPClient()

    # ensure workstation exists (get-or-create)
    try:
        client.get_doc("Workstation", DEFAULT_WORKSTATION)
        print(f"Workstation {DEFAULT_WORKSTATION} exists")
    except ERPClientError:
        print(f"Workstation {DEFAULT_WORKSTATION} missing, creating...")
        client.insert_doc("Workstation", {
            "workstation_name": DEFAULT_WORKSTATION,
            "__newname": DEFAULT_WORKSTATION
        })

    dry = "--dry-run" in sys.argv
    created, updated, _ = sync_tags(client, dry_run=dry)
    print(f"Done: {created} created, {updated} updated (dry_run={dry})")