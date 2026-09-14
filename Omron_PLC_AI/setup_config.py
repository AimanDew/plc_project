import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_schema import get_connection, set_config, init_database
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
set_config("target_oee_pct", "85.0")
set_config("target_availability_pct", "90.0")
set_config("target_performance_pct", "95.0")
set_config("target_quality_pct", "99.0")

print("Config set:")
print(f"  ideal_cycle_time_sec = 2.0")
print(f"  planned_time_min = 480 (8hr shift)")
print(f"  machine_unit = OEE")
print(f"  targets: A=90% P=95% Q=99% OEE=85%")

# Shifts
conn = get_connection()
cur = conn.cursor()

cur.execute("DELETE FROM shifts")
cur.execute("""
    INSERT INTO shifts (name, start_time, end_time, days_of_week, planned_downtime_min)
    VALUES (?, ?, ?, ?, ?)
""", ("Morning", "08:00", "16:00", "Mon,Tue,Wed,Thu,Fri", 60))
cur.execute("""
    INSERT INTO shifts (name, start_time, end_time, days_of_week, planned_downtime_min)
    VALUES (?, ?, ?, ?, ?)
""", ("Evening", "16:00", "00:00", "Mon,Tue,Wed,Thu,Fri", 60))
cur.execute("""
    INSERT INTO shifts (name, start_time, end_time, days_of_week, planned_downtime_min)
    VALUES (?, ?, ?, ?, ?)
""", ("Saturday", "08:00", "16:00", "Sat", 30))

# Downtime reasons
cur.execute("DELETE FROM downtime_reasons")
reasons = [
    (10, "Emergency Stop pressed", "Safety"),
    (20, "Red tower light (error)", "Fault"),
    (30, "Not in OEE mode", "Operational"),
    (40, "Manual mode selected", "Operational"),
    (50, "Idle - no active signals", "Idle"),
    (60, "Material shortage", "External"),
    (70, "Planned maintenance", "Planned"),
    (80, "Changeover / setup", "Planned"),
    (90, "Break / lunch", "Planned"),
    (99, "Unknown / other", "Uncategorized"),
]
for code, desc, cat in reasons:
    cur.execute("INSERT OR REPLACE INTO downtime_reasons VALUES (?, ?, ?)", (code, desc, cat))

conn.commit()
conn.close()

print(f"\nShifts: 3 (Morning, Evening, Saturday)")
print(f"Downtime reasons: {len(reasons)} codes")
print("\nDone.")