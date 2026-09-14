from db_schema import (
    get_config,
    get_reject_count_since,
    get_latest_ok_count,
    insert_oee_result
)


def calculate_oee(period_start, period_end, shift_id=None):
    """
    Calculate OEE for a given time period.

    Requires Layer 2 config:
    - 'ideal_cycle_time_sec' in oee_config
    - 'planned_time_min' in oee_config (or passed via shift_id)

    Returns dict with all OEE components.
    """

    # ==========================
    # LOAD CONFIG
    # ==========================
    ideal_cycle_sec = float(get_config("ideal_cycle_time_sec", "2.0"))
    planned_time_min = float(get_config("planned_time_min", "480"))

    # ==========================
    # COUNTS
    # ==========================
    ok_count = get_latest_ok_count()
    reject_count = get_reject_count_since(period_start)
    total_count = ok_count + reject_count

    # ==========================
    # RUN TIME & DOWNTIME
    # ==========================
    from db_schema import get_connection
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

    # ==========================
    # AVAILABILITY
    # ==========================
    if planned_time_min > 0:
        availability = run_time_min / planned_time_min
    else:
        availability = 0.0

    # ==========================
    # PERFORMANCE
    # ==========================
    if run_time_min > 0 and ideal_cycle_sec > 0:
        performance = (ideal_cycle_sec * total_count) / (run_time_min * 60)
    else:
        performance = 0.0

    if performance > 1.0:
        performance = 1.0

    # ==========================
    # QUALITY
    # ==========================
    if total_count > 0:
        quality = ok_count / total_count
    else:
        quality = 1.0

    # ==========================
    # OEE
    # ==========================
    oee = availability * performance * quality

    result = {
        "period_start": period_start,
        "period_end": period_end,
        "shift_id": shift_id,
        "planned_time_min": planned_time_min,
        "run_time_min": run_time_min,
        "downtime_min": downtime_min,
        "total_count": total_count,
        "good_count": ok_count,
        "reject_count": reject_count,
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
        period_start, period_end, shift_id,
        planned_time_min, run_time_min, downtime_min,
        total_count, ok_count, reject_count,
        ideal_cycle_sec,
        availability, performance, quality, oee
    )

    return result