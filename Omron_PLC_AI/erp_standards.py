import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_schema import get_connection, get_config
from erp_client import ERPClient, ERPClientError


DEFAULT_WORKSTATION = "WS-OEE-001"

# SQLite fallbacks (the old fake standards), used only when ERP is unreachable
FALLBACK = {
    "ideal_cycle_time_sec": 2.0,
    "planned_time_min": 480.0,
    "source": "local_config"
}


def _hours_overlap_minutes(work_hours, period_start, period_end):
    """Sum of working-hour minutes that fall inside [period_start, period_end].

    Note: ERPNext v16 'Workstation Working Hour' child table has no day field —
    rows are daily windows (start_time/end_time), deduplicated.
    """
    total_min = 0.0

    # dedupe identical windows (UI often adds several identical rows)
    unique_windows = set()
    for wh in work_hours:
        try:
            start_h = datetime.strptime(str(wh["start_time"]), "%H:%M:%S").time()
            end_h = datetime.strptime(str(wh["end_time"]), "%H:%M:%S").time()
        except (ValueError, TypeError):
            continue
        unique_windows.add((start_h, end_h))

    cur_date = period_start.date()
    end_date = period_end.date()

    while cur_date <= end_date:
        for (start_h, end_h) in unique_windows:
            window_start = datetime.combine(cur_date, start_h)
            window_end = datetime.combine(cur_date, end_h)
            if window_end <= window_start:
                # overnight window (e.g. 16:00 -> 00:00): treat end as next-day
                window_end += timedelta(days=1)

            overlap_start = max(window_start, period_start)
            overlap_end = min(window_end, period_end)
            if overlap_start < overlap_end:
                total_min += (overlap_end - overlap_start).total_seconds() / 60.0
        cur_date += timedelta(days=1)

    return total_min


def get_erp_standards(client=None, workstation=DEFAULT_WORKSTATION):

    """Pull OEE standards from ERPNext. Returns dict or None if unreachable."""

    client = client or ERPClient()

    try:

        # 1. workstation standards (working hours + capacity)
        ws = client.get_workstation_standards(workstation)
        if not ws:
            return None

        # 2. active job card -> work order -> bom -> operation time
        jc = client.get_active_job_card(workstation)
        cycle_time_sec = None
        bom_no = None

        if jc:
            wo = client.get_work_order_standards(jc["work_order"])
            bom_no = wo.get("bom_no")
            if bom_no:
                ops = client.get_bom_operation_standards(bom_no)
                # sum operation times that run on this workstation
                total_sec = 0.0
                for op in ops:
                    if op.get("workstation") == workstation and op.get("time_in_mins"):
                        total_sec += float(op["time_in_mins"]) * 60.0
                if total_sec > 0:
                    cycle_time_sec = total_sec

        return {
            "workstation": ws["name"],
            "working_hours": ws.get("working_hours", []),
            "production_capacity_per_hr": float(ws["production_capacity"]) if ws.get("production_capacity") else None,
            "cycle_time_sec": cycle_time_sec,
            "bom_no": bom_no,
            "source": "erp"
        }

    except (ERPClientError, Exception):
        return None


def compute_planned_time_min(standards, period_start, period_end):

    """Planned time = working-hours overlap within the period (ERP schedule).
    Falls back to capacity-based or config if hours are missing."""

    hours = standards.get("working_hours") or []
    if hours:
        planned = _hours_overlap_minutes(hours, period_start, period_end)
        if planned > 0:
            return planned

    # fallback: capacity-based estimate from period length
    return (period_end - period_start).total_seconds() / 60.0


def get_standards_for_period(period_start, period_end, client=None):

    """Main entry: try ERP first, fall back to SQLite config, then hardcoded."""

    period_start = period_start if isinstance(period_start, datetime) else datetime.fromisoformat(period_start)
    period_end = period_end if isinstance(period_end, datetime) else datetime.fromisoformat(period_end)

    try:
        standards = get_erp_standards(client)
    except Exception:
        standards = None

    if standards:
        planned_min = compute_planned_time_min(standards, period_start, period_end)
        cycle = standards.get("cycle_time_sec")
        if not cycle:
            # derive from capacity: 30/hr -> 120 s/unit
            cap = standards.get("production_capacity_per_hr")
            cycle = 3600.0 / cap if cap else None
        if not cycle:
            cycle = float(get_config("ideal_cycle_time_sec", FALLBACK["ideal_cycle_time_sec"]))

        return {
            "planned_time_min": planned_min,
            "ideal_cycle_time_sec": cycle,
            "workstation": standards.get("workstation"),
            "bom_no": standards.get("bom_no"),
            "source": "erp"
        }

    # full fallback: old local-config path
    return {
        "planned_time_min": float(get_config("planned_time_min", FALLBACK["planned_time_min"])),
        "ideal_cycle_time_sec": float(get_config("ideal_cycle_time_sec", FALLBACK["ideal_cycle_time_sec"])),
        "source": "local_config"
    }


if __name__ == "__main__":

    end = datetime.now()
    start = end - timedelta(hours=8)
    s = get_standards_for_period(start, end)
    print("Standards for last 8h:")
    for k, v in s.items():
        print(f"  {k}: {v}")