import json
from db_schema import (
    get_config,
    get_reject_count_since,
    get_latest_count,
    insert_oee_result,
    get_connection,
    enqueue_outbox_event
)


def _get_standards(period_start, period_end):
    """ERP standards first, SQLite config fallback."""
    try:
        from erp_standards import get_standards_for_period
        return get_standards_for_period(period_start, period_end)
    except Exception:
        return {
            "planned_time_min": float(get_config("planned_time_min", "480")),
            "ideal_cycle_time_sec": float(get_config("ideal_cycle_time_sec", "2.0")),
            "source": "local_config"
        }


def calculate_oee(period_start, period_end, shift_id=None):
    """
    Calculate OEE for a given time period using Omron PLC data.
    Standards (planned time, cycle time) come from ERPNext when reachable
    (Workstation working hours + BOM operation time); local config otherwise.
    """

    standards = _get_standards(period_start, period_end)
    ideal_cycle_sec = standards["ideal_cycle_time_sec"]
    planned_time_min = standards["planned_time_min"]
    standards_source = standards.get("source", "unknown")

    ok_count = get_latest_count("OK Count")
    ng_count = get_latest_count("NG Count")
    total_count = ok_count + ng_count

    conn = get_connection()
    cur = conn.cursor()

    downtime_rows = cur.execute("""
        SELECT duration_sec FROM downtime_events
        WHERE start_time >= ? AND end_time <= ?
    """, (period_start, period_end)).fetchall()

    conn.close()

    downtime_sec = sum(r[0] for r in downtime_rows if r[0] is not None)
    downtime_min = downtime_sec / 60.0
    run_time_min = planned_time_min - downtime_min

    if planned_time_min > 0:
        availability = run_time_min / planned_time_min
    else:
        availability = 0.0

    if run_time_min > 0 and ideal_cycle_sec > 0:
        performance = (ideal_cycle_sec * total_count) / (run_time_min * 60)
    else:
        performance = 0.0

    if performance > 1.0:
        performance = 1.0

    if total_count > 0:
        quality = ok_count / total_count
    else:
        quality = 1.0

    oee = availability * performance * quality

    result = {
        "period_start": period_start,
        "period_end": period_end,
        "standards_source": standards_source,
        "planned_time_min": planned_time_min,
        "run_time_min": run_time_min,
        "downtime_min": downtime_min,
        "total_count": total_count,
        "good_count": ok_count,
        "reject_count": ng_count,
        "ideal_cycle_time_sec": ideal_cycle_sec,
        "availability": availability,
        "performance": performance,
        "quality": quality,
        "oee": oee,
        "availability_pct": round(availability * 100, 1),
        "performance_pct": round(performance * 100, 1),
        "quality_pct": round(quality * 100, 1),
        "oee_pct": round(oee * 100, 1)
    }

    insert_oee_result(
        period_start, period_end,
        planned_time_min, run_time_min, downtime_min,
        total_count, ok_count, ng_count,
        ideal_cycle_sec,
        availability, performance, quality, oee
    )

    enqueue_outbox_event("oee_result", {
        "machine_unit": "OEE",
        "timestamp": period_end,
        "state": "OEE",
        "reason": "periodic calculation",
        "raw_payload": json.dumps(result, default=str)
    })

    return result