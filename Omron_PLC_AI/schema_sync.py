import argparse
import difflib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from erp_client import ERPClient, ERPClientError


# The two custom DocTypes that, per project history, exist only as live
# schema - rebuilt by hand on each ERPNext instance, never checked in.
# This is the whole list this tool knows how to track; add a name here
# once it has a JSON file under erp_schema/doctypes/.
TRACKED_DOCTYPES = ["Machine Event", "PLC Tag"]

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "erp_schema", "doctypes")

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


def tracked_path(doctype):

    return os.path.join(SCHEMA_DIR, doctype + ".json")


def fetch_live(client, doctype):

    try:
        return client.get_doc("DocType", doctype)
    except ERPClientError as e:
        if e.status_code == 404:
            return None
        raise


def cmd_export(client, doctypes):

    os.makedirs(SCHEMA_DIR, exist_ok=True)
    for dt in doctypes:
        live = fetch_live(client, dt)
        if live is None:
            print(f"  ! {dt}: does not exist on {client.base_url}, skipped")
            continue
        with open(tracked_path(dt), "w", encoding="utf-8") as f:
            f.write(normalize(live))
        print(f"  exported {dt} -> {tracked_path(dt)}")


def cmd_check(client, doctypes):

    clean = True
    for dt in doctypes:
        path = tracked_path(dt)
        if not os.path.exists(path):
            print(f"  ? {dt}: not tracked yet (run `export` first)")
            clean = False
            continue

        with open(path, "r", encoding="utf-8") as f:
            tracked = f.read()

        live = fetch_live(client, dt)
        if live is None:
            print(f"  ! {dt}: tracked in repo but MISSING on {client.base_url}")
            clean = False
            continue

        live_norm = normalize(live)
        if tracked == live_norm:
            print(f"  = {dt}: matches repo")
        else:
            clean = False
            print(f"  x {dt}: DRIFTED from repo")
            diff = difflib.unified_diff(
                tracked.splitlines(), live_norm.splitlines(),
                fromfile=f"repo/{dt}.json", tofile=f"live ({client.base_url})",
                lineterm=""
            )
            for line in diff:
                print("      " + line)

    return clean


def cmd_apply(client, doctypes):

    for dt in doctypes:
        path = tracked_path(dt)
        if not os.path.exists(path):
            print(f"  ? {dt}: not tracked, nothing to apply")
            continue

        with open(path, "r", encoding="utf-8") as f:
            target = json.load(f)

        live = fetch_live(client, dt)
        if live is None:
            client.insert_doc("DocType", target)
            print(f"  + {dt}: created on {client.base_url}")
        else:
            target["name"] = dt
            client.save_doc(target)
            print(f"  ~ {dt}: updated on {client.base_url}")


def main():

    parser = argparse.ArgumentParser(
        description="Version-control check/sync for custom ERPNext DocTypes "
                    "(Machine Event, PLC Tag) against erp_schema/doctypes/."
    )
    parser.add_argument("action", choices=["export", "check", "apply"])
    parser.add_argument("doctypes", nargs="*", default=TRACKED_DOCTYPES)
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

    if args.action == "export":
        cmd_export(client, args.doctypes)
    elif args.action == "check":
        clean = cmd_check(client, args.doctypes)
        sys.exit(0 if clean else 1)
    elif args.action == "apply":
        cmd_apply(client, args.doctypes)


if __name__ == "__main__":
    main()
