import sys
import os
from datetime import datetime, timedelta
import html as html_mod

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import HTMLResponse, JSONResponse
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from db_schema import get_connection
from state_classifier import classify_state


def get_live_tags():
    conn = get_connection()
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT tag_name, value FROM tag_readings
        WHERE id IN (SELECT MAX(id) FROM tag_readings GROUP BY tag_name)
    """).fetchall()
    conn.close()
    if not rows:
        return None
    tags = {}
    for name, val in rows:
        if val == "True":
            tags[name] = True
        elif val == "False":
            tags[name] = False
        else:
            try:
                tags[name] = int(val)
            except ValueError:
                try:
                    tags[name] = float(val)
                except ValueError:
                    tags[name] = val
    return tags


def get_last_reading_timestamp():
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("SELECT MAX(timestamp) FROM tag_readings").fetchone()
    conn.close()
    return row[0] if row and row[0] else None


def get_state_distribution(since_hours=1):
    conn = get_connection()
    cur = conn.cursor()
    since = (datetime.now() - timedelta(hours=since_hours)).isoformat()
    rows = cur.execute("""
        SELECT state, COUNT(*) as count
        FROM machine_states
        WHERE timestamp >= ?
        GROUP BY state
    """, (since,)).fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}


def get_recent_transitions(limit=10):
    conn = get_connection()
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT timestamp, from_state, to_state, reason, duration_sec
        FROM state_transitions
        ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows


def get_recent_downtime(limit=10):
    conn = get_connection()
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT start_time, end_time, duration_sec, reason, machine_unit
        FROM downtime_events
        ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows


def get_recent_rejects(limit=10):
    conn = get_connection()
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT timestamp FROM reject_events
        ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows


def get_counts():
    conn = get_connection()
    cur = conn.cursor()
    ok = cur.execute("""
        SELECT value FROM tag_readings
        WHERE tag_name = 'OEE Out OK Count'
        ORDER BY id DESC LIMIT 1
    """).fetchone()
    rejects = cur.execute("SELECT COUNT(*) FROM reject_events").fetchone()
    conn.close()
    return {
        "ok_count": int(ok[0]) if ok else 0,
        "reject_count": rejects[0] if rejects else 0
    }


def get_config():
    conn = get_connection()
    cur = conn.cursor()
    rows = cur.execute("SELECT key, value FROM oee_config").fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}


def get_latest_oee():
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("""
        SELECT period_start, period_end, availability, performance, quality, oee,
               good_count, reject_count, total_count, run_time_min, downtime_min
        FROM oee_results
        ORDER BY id DESC LIMIT 1
    """).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "period_start": row[0], "period_end": row[1],
        "availability": row[2], "performance": row[3],
        "quality": row[4], "oee": row[5],
        "good_count": row[6], "reject_count": row[7],
        "total_count": row[8], "run_time_min": row[9], "downtime_min": row[10],
    }


def build_tag_grid(tags):
    rows = ""
    for name in sorted(tags.keys()):
        value = tags[name]
        val_class = "green" if value == True else ""
        rows += f'<div class="tag-item"><span class="name">{html_mod.escape(name)}</span><span class="val {val_class}">{value}</span></div>\n'
    return rows


def build_state_dist_table(state_dist):
    total = sum(state_dist.values()) if state_dist else 0
    rows = ""
    for state in ["RUNNING", "DOWN", "IDLE", "OFFLINE"]:
        count = state_dist.get(state, 0)
        pct = (count / total * 100) if total > 0 else 0
        rows += f'<tr><td><span class="state-badge state-{state.lower()}">{state}</span></td><td>{count}</td><td>{pct:.1f}%</td></tr>\n'
    return rows


def build_transitions_table(transitions):
    if not transitions:
        return '<p style="color:#888">No state transitions recorded.</p>'
    rows = ""
    for t in transitions:
        dur = f"{t[4]:.1f}" if t[4] else "-"
        rows += f'<tr><td>{t[0]}</td><td>{t[1] or "-"}</td><td>{t[2]}</td><td>{t[3] or "-"}</td><td>{dur}</td></tr>\n'
    return rows


def build_downtime_table(downtime):
    if not downtime:
        return '<p style="color:#888">No downtime events recorded.</p>'
    rows = ""
    for d in downtime:
        dur = f"{d[2]:.1f}" if d[2] else "-"
        end = d[1] or "OPEN"
        rows += f'<tr><td>{d[0]}</td><td>{end}</td><td>{dur}</td><td>{d[3] or "-"}</td><td>{d[4]}</td></tr>\n'
    return rows


def build_rejects_table(rejects):
    if not rejects:
        return '<p style="color:#888">No reject events recorded.</p>'
    rows = ""
    for r in rejects:
        rows += f'<tr><td>{r[0]}</td></tr>\n'
    return rows


def build_config_grid(config):
    rows = ""
    for key, val in sorted(config.items()):
        rows += f'<div class="config-item"><span class="key">{html_mod.escape(key)}:</span> <span class="val">{html_mod.escape(str(val))}</span></div>\n'
    return rows


def build_page():
    tags = get_live_tags()
    if tags is None:
        tags = {}
        data_color = "red"
        data_text = "NO DATA"
    else:
        latest_state = get_last_reading_timestamp()
        if latest_state:
            age_sec = (datetime.now() - datetime.fromisoformat(latest_state)).total_seconds()
            if age_sec < 10:
                data_color = "green"
                data_text = f"LIVE ({age_sec:.0f}s ago)"
            else:
                data_color = "yellow"
                data_text = f"CACHED ({age_sec:.0f}s ago)"
        else:
            data_color = "green"
            data_text = "LIVE"

    state, reason = classify_state(tags) if tags else ("UNKNOWN", "PLC offline")
    state_class = state.lower() if state else "offline"

    counts = get_counts()
    state_dist = get_state_distribution(1)
    transitions = get_recent_transitions(10)
    downtime = get_recent_downtime(10)
    rejects = get_recent_rejects(10)
    config = get_config()

    latest_oee = get_latest_oee()
    if latest_oee:
        avail = (latest_oee["availability"] or 0) * 100
        perf = (latest_oee["performance"] or 0) * 100
        qual = (latest_oee["quality"] or 0) * 100
        oee = (latest_oee["oee"] or 0) * 100
    else:
        avail = perf = qual = oee = 0

    if oee >= 85:
        oee_color = "green"
        oee_bar = "#4caf50"
    elif oee >= 50:
        oee_color = "yellow"
        oee_bar = "#ffc107"
    else:
        oee_color = "red"
        oee_bar = "#f44336"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OEE Dashboard</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }}
  body {{ background: #0f1419; color: #e0e0e0; padding: 20px; }}
  h1 {{ color: #4fc3f7; margin-bottom: 5px; }}
  .subtitle {{ color: #888; margin-bottom: 20px; font-size: 14px; }}
  .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }}
  .card {{ background: #1a1f2e; border-radius: 10px; padding: 20px; border: 1px solid #2a3040; }}
  .card h3 {{ color: #aaa; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }}
  .big-number {{ font-size: 28px; font-weight: bold; }}
  .green {{ color: #4caf50; }}
  .yellow {{ color: #ffc107; }}
  .red {{ color: #f44336; }}
  .blue {{ color: #4fc3f7; }}
  .section {{ background: #1a1f2e; border-radius: 10px; padding: 20px; border: 1px solid #2a3040; margin-bottom: 20px; }}
  .section h2 {{ color: #4fc3f7; margin-bottom: 15px; font-size: 18px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: left; color: #888; padding: 8px; border-bottom: 1px solid #2a3040; }}
  td {{ padding: 8px; border-bottom: 1px solid #1e2433; }}
  .tag-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }}
  .tag-item {{ background: #141821; padding: 8px 12px; border-radius: 6px; display: flex; justify-content: space-between; }}
  .tag-item .name {{ color: #aaa; }}
  .tag-item .val {{ font-weight: bold; }}
  .state-badge {{ padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }}
  .state-running {{ background: #2d4a2d; color: #4caf50; }}
  .state-down {{ background: #4a2d2d; color: #f44336; }}
  .state-idle {{ background: #4a402d; color: #ffc107; }}
  .state-offline {{ background: #333; color: #888; }}
  .state-unknown {{ background: #333; color: #888; }}
  .bar-container {{ background: #2a3040; border-radius: 4px; height: 8px; margin-top: 8px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 4px; }}
  .config-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; font-size: 13px; }}
  .config-item {{ background: #141821; padding: 8px 12px; border-radius: 6px; }}
  .config-item .key {{ color: #888; }}
  .config-item .val {{ color: #4fc3f7; font-weight: bold; }}
  .auto-refresh {{ color: #4caf50; font-size: 12px; margin-left: 10px; }}
  .updated {{ color: #555; font-size: 12px; margin-top: 10px; }}
</style>
<script>
setTimeout(function(){{ location.reload(); }}, 5000);
</script>
</head>
<body>

<h1>OEE Dashboard <span class="auto-refresh">(auto-refresh 5s)</span></h1>
<p class="subtitle">OEE_Briefcase_Discovery | DB3 "Data" | PLC 192.168.4.190</p>

<div class="grid">
  <div class="card">
    <h3>Machine State</h3>
    <div class="big-number"><span class="state-badge state-{state_class}">{state}</span></div>
  </div>
  <div class="card">
    <h3>OK Count (Good Parts)</h3>
    <div class="big-number green">{counts['ok_count']}</div>
  </div>
  <div class="card">
    <h3>Reject Count (NG Workaround)</h3>
    <div class="big-number red">{counts['reject_count']}</div>
  </div>
  <div class="card">
    <h3>PLC Connection</h3>
    <div class="big-number {data_color}">{data_text}</div>
  </div>
</div>

<div class="grid">
  <div class="card">
    <h3>Availability</h3>
    <div class="big-number blue">{avail:.1f}%</div>
    <div class="bar-container"><div class="bar-fill" style="width: {avail:.1f}%; background: #4fc3f7;"></div></div>
  </div>
  <div class="card">
    <h3>Performance</h3>
    <div class="big-number blue">{perf:.1f}%</div>
    <div class="bar-container"><div class="bar-fill" style="width: {perf:.1f}%; background: #4fc3f7;"></div></div>
  </div>
  <div class="card">
    <h3>Quality</h3>
    <div class="big-number blue">{qual:.1f}%</div>
    <div class="bar-container"><div class="bar-fill" style="width: {qual:.1f}%; background: #4fc3f7;"></div></div>
  </div>
  <div class="card">
    <h3>OEE</h3>
    <div class="big-number {oee_color}">{oee:.1f}%</div>
    <div class="bar-container"><div class="bar-fill" style="width: {oee:.1f}%; background: {oee_bar};"></div></div>
  </div>
</div>

<div class="section">
  <h2>Live PLC Tags</h2>
  <div class="tag-grid">
{build_tag_grid(tags)}  </div>
</div>

<div class="section">
  <h2>State Distribution (Last 1 Hour)</h2>
  <table>
    <tr><th>State</th><th>Poll Count</th><th>% of Time</th></tr>
{build_state_dist_table(state_dist)}  </table>
</div>

<div class="section">
  <h2>Recent State Transitions</h2>
  <table>
    <tr><th>Timestamp</th><th>From</th><th>To</th><th>Reason</th><th>Duration (s)</th></tr>
{build_transitions_table(transitions)}  </table>
</div>

<div class="section">
  <h2>Recent Downtime Events</h2>
  <table>
    <tr><th>Start</th><th>End</th><th>Duration (s)</th><th>Reason</th><th>Unit</th></tr>
{build_downtime_table(downtime)}  </table>
</div>

<div class="section">
  <h2>Recent Reject Events</h2>
  <table>
    <tr><th>Timestamp</th></tr>
{build_rejects_table(rejects)}  </table>
</div>

<div class="section">
  <h2>OEE Configuration</h2>
  <div class="config-grid">
{build_config_grid(config)}  </div>
</div>

<p class="updated">Last updated: {datetime.now().isoformat()}</p>

</body>
</html>"""


def dashboard(request):
    return HTMLResponse(build_page())


def api_tags(request):
    tags = get_live_tags()
    if tags is None:
        return JSONResponse({"error": "No data available"}, status_code=503)
    return JSONResponse(tags)


def api_state(request):
    tags = get_live_tags()
    if tags is None:
        return JSONResponse({"error": "No data available"}, status_code=503)
    state, reason = classify_state(tags)
    return JSONResponse({"state": state, "reason": reason})


def api_counts(request):
    return JSONResponse(get_counts())


def api_oee(request):
    from oee_calculator import calculate_oee
    end = datetime.now()
    start = end - timedelta(hours=1)
    result = calculate_oee(start.isoformat(), end.isoformat())
    result["availability_pct"] = round(result["availability"] * 100, 1)
    result["performance_pct"] = round(result["performance"] * 100, 1)
    result["quality_pct"] = round(result["quality"] * 100, 1)
    result["oee_pct"] = round(result["oee"] * 100, 1)
    return JSONResponse(result)


routes = [
    Route("/", dashboard),
    Route("/api/tags", api_tags),
    Route("/api/state", api_state),
    Route("/api/counts", api_counts),
    Route("/api/oee", api_oee),
]

middleware = [
    Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
]

app = Starlette(routes=routes, middleware=middleware)


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("OEE Dashboard starting...")
    print("  http://localhost:8000")
    print("=" * 50)
    uvicorn.run(app, host="127.0.0.1", port=8000)