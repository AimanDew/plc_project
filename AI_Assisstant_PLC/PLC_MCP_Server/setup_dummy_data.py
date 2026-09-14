import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_schema import get_connection, set_config


def insert_shift(name, start_time, end_time, days_of_week, planned_downtime_min):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO shifts (name, start_time, end_time, days_of_week, planned_downtime_min)
        VALUES (?, ?, ?, ?, ?)
    """, (name, start_time, end_time, days_of_week, planned_downtime_min))
    conn.commit()
    conn.close()


def insert_downtime_reason(code, description, category):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO downtime_reasons (code, description, category)
        VALUES (?, ?, ?)
    """, (code, description, category))
    conn.commit()
    conn.close()


def insert_production_run(start_time, ok_count_start):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO production_runs (start_time, ok_count_start)
        VALUES (?, ?)
    """, (start_time, ok_count_start))
    run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return run_id


print("=" * 60)
print("POPULATING DUMMY OEE CONFIG (LAYER 2)")
print("=" * 60)

# ==========================
# 1. OEE CONFIG (key-value)
# ==========================
print("\n[1] OEE Config values:")
set_config("ideal_cycle_time_sec", "2.0")
set_config("planned_time_min", "480")
set_config("machine_unit", "OEE")
set_config("target_oee_pct", "85.0")
set_config("target_availability_pct", "90.0")
set_config("target_performance_pct", "95.0")
set_config("target_quality_pct", "99.0")
print("    ideal_cycle_time_sec = 2.0")
print("    planned_time_min = 480 (8 hour shift)")
print("    machine_unit = OEE")
print("    target_oee_pct = 85.0")
print("    target_availability_pct = 90.0")
print("    target_performance_pct = 95.0")
print("    target_quality_pct = 99.0")

# ==========================
# 2. SHIFTS
# ==========================
print("\n[2] Shift schedules:")
insert_shift("Morning",  "08:00", "16:00", "Mon,Tue,Wed,Thu,Fri", 60)
insert_shift("Evening",  "16:00", "00:00", "Mon,Tue,Wed,Thu,Fri", 60)
insert_shift("Night",    "00:00", "08:00", "Mon,Tue,Wed,Thu,Fri", 60)
insert_shift("Saturday", "08:00", "16:00", "Sat", 30)
insert_shift("Sunday",   "08:00", "16:00", "Sun", 30)
print("    Morning  08:00-16:00 Mon-Fri (60 min planned downtime)")
print("    Evening  16:00-00:00 Mon-Fri (60 min planned downtime)")
print("    Night    00:00-08:00 Mon-Fri (60 min planned downtime)")
print("    Saturday 08:00-16:00 Sat    (30 min planned downtime)")
print("    Sunday   08:00-16:00 Sun    (30 min planned downtime)")

# ==========================
# 3. DOWNTIME REASONS
# ==========================
print("\n[3] Downtime reason codes:")

reasons = [
    (10, "OEE E-Stop pressed",        "Safety"),
    (11, "DG E-Stop pressed",         "Safety"),
    (20, "OEE Machine Error",         "Fault"),
    (21, "DG Machine Error",          "Fault"),
    (30, "OEE Machine idle (no auto)", "Operational"),
    (31, "DG Machine idle",           "Operational"),
    (40, "Machine OK but not running", "Idle"),
    (50, "Both DG and OEE disabled",  "Offline"),
    (60, "Material shortage",         "External"),
    (70, "Planned maintenance",       "Planned"),
    (80, "Changeover / setup",        "Planned"),
    (90, "Break / lunch",             "Planned"),
    (99, "Unknown / other",           "Uncategorized"),
]

for code, desc, cat in reasons:
    insert_downtime_reason(code, desc, cat)
    print(f"    {code:3d} | {cat:<12} | {desc}")

# ==========================
# 4. PRODUCTION RUN (current)
# ==========================
print("\n[4] Production run (started now):")
run_id = insert_production_run(datetime.now().isoformat(), 0)
print(f"    Run ID: {run_id}")
print(f"    Start:  {datetime.now().isoformat()}")
print(f"    OK count at start: 0")

# ==========================
# 5. VERIFY
# ==========================
print("\n[5] Verification:")
conn = get_connection()
cur = conn.cursor()

config_count = cur.execute("SELECT COUNT(*) FROM oee_config").fetchone()[0]
shift_count = cur.execute("SELECT COUNT(*) FROM shifts").fetchone()[0]
reason_count = cur.execute("SELECT COUNT(*) FROM downtime_reasons").fetchone()[0]
run_count = cur.execute("SELECT COUNT(*) FROM production_runs").fetchone()[0]

print(f"    oee_config:         {config_count} entries")
print(f"    shifts:             {shift_count} shifts")
print(f"    downtime_reasons:   {reason_count} reason codes")
print(f"    production_runs:    {run_count} runs")

conn.close()

print("\n" + "=" * 60)
print("DUMMY CONFIG COMPLETE")
print("=" * 60)
print("All Layer 2 (human) config populated with test values.")
print("Edit shifts/reasons directly in SQLite or via set_config()")