import argparse
import difflib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from erp_client import ERPClient, ERPClientError


# Schema-only customizations that, per project history, exist only as live
# schema - rebuilt by hand on each ERPNext instance, never checked in. Each
# entry is (meta_doctype, name): meta_doctype is the doctype the object
# itself is stored as ("DocType" for a whole custom doctype, "Custom Field"
# for a field bolted onto a standard one); name is that record's own name.
# This is the whole list this tool knows how to track; add an entry here
# once it has a JSON file under erp_schema/.
TRACKED = [
    ("DocType", "Machine Event"),
    ("DocType", "PLC Tag"),
    ("Custom Field", "Work Order-custom_priority"),
]

BASE_SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "erp_schema")
SCHEMA_SUBDIR = {"DocType": "doctypes", "Custom Field": "custom_fields"}

# Per-instance/per-save metadata that carries no schema meaning - stripped
# before comparing or writing to the repo, so a diff only ever shows an
# actual field/behavior change, never "who saved it last on which instance."
VOLATILE_KEYS = {
    "owner", "creation", "modified", "modified_by",
    "_comments", "_assign", "_liked_by", "_user_tags", "lastsync",
}


def strip_volatile(obj):

    if isinstance(obj, dict):
        return {k: strip_volatile(v) for k, v in obj.items() if k not in VOLATILE_KEYS}
    if isinstance(obj, list):
        return [strip_volatile(v) for v in obj]
    return obj


def normalize(doc):

    data = doc.get("data", doc) if isinstance(doc, dict) else doc
    return json.dumps(strip_volatile(data), indent=2, sort_keys=True) + "\n"


def tracked_path(meta_doctype, name):

    subdir = SCHEMA_SUBDIR[meta_doctype]
    return os.path.join(BASE_SCHEMA_DIR, subdir, name + ".json")


def fetch_live(client, meta_doctype, name):

    try:
        return client.get_doc(meta_doctype, name)
    except ERPClientError as e:
        if e.status_code == 404:
            return None
        raise


def cmd_export(client, items):

    for meta_doctype, name in items:
        os.makedirs(os.path.join(BASE_SCHEMA_DIR, SCHEMA_SUBDIR[meta_doctype]), exist_ok=True)
        live = fetch_live(client, meta_doctype, name)
        if live is None:
            print(f"  ! {name}: does not exist on {client.base_url}, skipped")
            continue
        path = tracked_path(meta_doctype, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(normalize(live))
        print(f"  exported {name} -> {path}")


def cmd_check(client, items):

    clean = True
    for meta_doctype, name in items:
        path = tracked_path(meta_doctype, name)
        if not os.path.exists(path):
            print(f"  ? {name}: not tracked yet (run `export` first)")
            clean = False
            continue

        with open(path, "r", encoding="utf-8") as f:
            tracked = f.read()

        live = fetch_live(client, meta_doctype, name)
        if live is None:
            print(f"  ! {name}: tracked in repo but MISSING on {client.base_url}")
            clean = False
            continue

        live_norm = normalize(live)
        if tracked == live_norm:
            print(f"  = {name}: matches repo")
        else:
            clean = False
            print(f"  x {name}: DRIFTED from repo")
            diff = difflib.unified_diff(
                tracked.splitlines(), live_norm.splitlines(),
                fromfile=f"repo/{name}.json", tofile=f"live ({client.base_url})",
                lineterm=""
            )
            for line in diff:
                print("      " + line)

    return clean


def cmd_apply(client, items):

    for meta_doctype, name in items:
        path = tracked_path(meta_doctype, name)
        if not os.path.exists(path):
            print(f"  ? {name}: not tracked, nothing to apply")
            continue

        with open(path, "r", encoding="utf-8") as f:
            target = json.load(f)

        live = fetch_live(client, meta_doctype, name)
        if live is None:
            client.insert_doc(meta_doctype, target)
            print(f"  + {name}: created on {client.base_url}")
        else:
            target["name"] = name
            client.save_doc(target)
            print(f"  ~ {name}: updated on {client.base_url}")


def main():

    parser = argparse.ArgumentParser(
        description="Version-control check/sync for custom ERPNext schema "
                    "objects (custom DocTypes and Custom Fields) against erp_schema/."
    )
    parser.add_argument("action", choices=["export", "check", "apply"])
    parser.add_argument("names", nargs="*", help="filter TRACKED by name; default is all of it")
    parser.add_argument(
        "--config",
        help="path to an erp_config.json-shaped file. Default: whatever "
             "erp_config.json next to this script points at - currently the "
             "local dev instance. Use this to point at a different instance "
             "without changing the default target."
    )
    args = parser.parse_args()

    config = None
    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)

    client = ERPClient(config=config)
    print(f"target: {client.base_url}")

    items = [t for t in TRACKED if t[1] in args.names] if args.names else TRACKED

    if args.action == "export":
        cmd_export(client, items)
    elif args.action == "check":
        clean = cmd_check(client, items)
        sys.exit(0 if clean else 1)
    elif args.action == "apply":
        cmd_apply(client, items)


if __name__ == "__main__":
    main()
