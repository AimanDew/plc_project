import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "Omron_PLC_AI"))
sys.path.insert(0, PROJECT_ROOT)

from erp_client import ERPClient, ERPClientError
from erp_common import builders, plumbing


# The real, hardware-verified Siemens map (session history: verified against
# the live OEE-briefcase PLC on 2026-08-19). Reused as-is - see plc_project's
# session log for why this wasn't re-extracted from TIA Portal for this task.
SIEMENS_MAP = os.path.join(
    os.path.dirname(HERE), "AI_Assisstant_PLC", "PLC_MCP_Server", "tag_map.json"
)
MITSUBISHI_MAP = os.path.join(HERE, "mitsubishi_tag_map.json")

SIEMENS_WORKSTATION = "WS-SIEMENS-001"
MITSUBISHI_WORKSTATION = "WS-MITSU-001"


def siemens_address(db, info):

    # Real Snap7/TIA Portal notation: DBX (bit), DBB (byte), DBW (16-bit
    # word/int), DBD (32-bit double word - real or dint).
    byte = info["byte"]
    t = info["type"]

    if t == "bool":
        return f"DB{db}.DBX{byte}.{info['bit']}"
    if t == "usint":
        return f"DB{db}.DBB{byte}"
    if t == "int":
        return f"DB{db}.DBW{byte}"
    if t == "real":
        return f"DB{db}.DBD{byte}"
    return f"DB{db}.byte{byte}"


def load_siemens_tags():

    with open(SIEMENS_MAP, "r", encoding="utf-8") as f:
        raw = json.load(f)

    db = raw["db"]
    return {
        name: {
            "address": siemens_address(db, info),
            "type": info["type"],
            "comment": "",
        }
        for name, info in raw["tags"].items()
    }


def load_mitsubishi_tags():

    with open(MITSUBISHI_MAP, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw["tags"]


def ensure_workstation(client, name):

    try:
        client.get_doc("Workstation", name)
        print(f"  Workstation {name} exists")
    except ERPClientError as e:
        if e.status_code != 404:
            raise
        client.insert_doc("Workstation", builders.workstation(name))
        print(f"  Workstation {name} created")


def push_tags(client, tags, workstation, protocol, dry_run=False):

    created, updated, skipped = 0, 0, 0

    for tag_name, info in tags.items():

        existing = None
        try:
            result = client.get_doc_list(
                "PLC Tag", filters=[["tag_name", "=", tag_name]], limit=1
            )
            data = plumbing.unwrap(result)
            existing = data[0] if data else None
        except ERPClientError:
            existing = None

        # tag_name is globally unique (autoname: field:tag_name) - a name
        # collision with a DIFFERENT workstation's existing tag would
        # silently reassign someone else's row instead of creating a new
        # one. Refuse rather than risk that.
        if existing and existing.get("workstation") not in (None, "", workstation):
            print(f"  ! SKIP {tag_name}: already exists on {existing.get('workstation')!r}, not {workstation!r}")
            skipped += 1
            continue

        fields = builders.plc_tag(
            tag_name=tag_name, protocol=protocol, address=info["address"],
            data_type=info["type"], workstation=workstation,
            comment=info.get("comment", ""),
        )

        if dry_run:
            action = "update" if existing else "create"
            print(f"  [dry] would {action} {tag_name} ({info['address']}) -> {workstation}")
            continue

        if existing:
            client.update_doc("PLC Tag", existing["name"], fields)
            updated += 1
        else:
            client.insert_doc("PLC Tag", fields)
            created += 1
            print(f"  + {tag_name} ({info['address']}) -> {workstation}")

    return created, updated, skipped


if __name__ == "__main__":

    dry = "--dry-run" in sys.argv
    client = ERPClient()

    print(f"=== Siemens (real, verified 2026-08-19) -> {SIEMENS_WORKSTATION} ===")
    ensure_workstation(client, SIEMENS_WORKSTATION)
    c, u, s = push_tags(client, load_siemens_tags(), SIEMENS_WORKSTATION, "S7", dry_run=dry)
    print(f"  {c} created, {u} updated, {s} skipped")

    print(f"=== Mitsubishi (fabricated) -> {MITSUBISHI_WORKSTATION} ===")
    ensure_workstation(client, MITSUBISHI_WORKSTATION)
    c, u, s = push_tags(client, load_mitsubishi_tags(), MITSUBISHI_WORKSTATION, "MC", dry_run=dry)
    print(f"  {c} created, {u} updated, {s} skipped")
