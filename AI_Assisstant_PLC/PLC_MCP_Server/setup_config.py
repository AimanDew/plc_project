import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_schema import set_config, init_database, get_config
import json

TAG_MAP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tag_map.json")

with open(TAG_MAP_PATH, "r", encoding="utf-8") as f:
    tag_map = json.load(f)

init_database(tag_map)
print("Database initialized with full OEE schema")

print("\nSetting default OEE config...")

set_config("ideal_cycle_time_sec", "2.0")
set_config("planned_time_min", "480")
set_config("machine_unit", "OEE")

print("Config set:")
print(f"  ideal_cycle_time_sec = {get_config('ideal_cycle_time_sec')}")
print(f"  planned_time_min     = {get_config('planned_time_min')}")
print(f"  machine_unit         = {get_config('machine_unit')}")

print("\nDone. You can change these later via set_config() or update oee_config table directly.")