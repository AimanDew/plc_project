import sqlite3
import os
import json


DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "omron_plc_tags.db"
)


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_database(tag_map):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            name        TEXT PRIMARY KEY,
            address     TEXT,
            data_type   TEXT,
            comment     TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tag_readings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            tag_name    TEXT NOT NULL,
            data_type   TEXT NOT NULL,
            value       TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS machine_states (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            state       TEXT NOT NULL,
            reason      TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS state_transitions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT NOT NULL,
            from_state      TEXT,
            to_state        TEXT NOT NULL,
            reason          TEXT,
            duration_sec    REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS downtime_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time      TEXT NOT NULL,
            end_time        TEXT,
            duration_sec    REAL,
            reason          TEXT,
            machine_unit     TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS reject_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS oee_config (
            key     TEXT PRIMARY KEY,
            value   TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS shifts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            start_time  TEXT NOT NULL,
            end_time    TEXT NOT NULL,
            days_of_week TEXT NOT NULL,
            planned_downtime_min INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS downtime_reasons (
            code        INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            category    TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS oee_results (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            period_start        TEXT NOT NULL,
            period_end          TEXT NOT NULL,
            planned_time_min    REAL,
            run_time_min        REAL,
            downtime_min        REAL,
            total_count         INTEGER,
            good_count          INTEGER,
            reject_count        INTEGER,
            ideal_cycle_time_sec REAL,
            availability        REAL,
            performance         REAL,
            quality             REAL,
            oee                 REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS outbox_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            event_uuid      TEXT NOT NULL UNIQUE,
            event_type      TEXT NOT NULL,
            payload         TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pending',
            attempts        INTEGER NOT NULL DEFAULT 0,
            last_error      TEXT,
            created_at      TEXT NOT NULL,
            synced_at       TEXT
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_outbox_status
        ON outbox_events (status, id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_tag_readings_ts
        ON tag_readings (timestamp)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_downtime_unit_open
        ON downtime_events (machine_unit, end_time)
    """)

    for name, info in tag_map["tags"].items():
        cur.execute("""
            INSERT OR REPLACE INTO tags (name, address, data_type, comment)
            VALUES (?, ?, ?, ?)
        """, (
            name,
            info["address"],
            info["type"],
            info.get("comment", "")
        ))

    conn.commit()
    conn.close()


def enqueue_outbox_event(event_type, payload, event_uuid=None):
    from datetime import datetime
    import uuid

    if event_uuid is None:
        event_uuid = str(uuid.uuid4())

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT OR IGNORE INTO outbox_events
                (event_uuid, event_type, payload, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
        """, (
            event_uuid,
            event_type,
            json.dumps(payload, default=str),
            datetime.now().isoformat()
        ))
        conn.commit()
        return event_uuid
    finally:
        conn.close()


def get_pending_outbox_events(limit=50):
    conn = get_connection()
    try:
        cur = conn.cursor()
        rows = cur.execute("""
            SELECT id, event_uuid, event_type, payload, attempts
            FROM outbox_events
            WHERE status = 'pending'
            ORDER BY id ASC
            LIMIT ?
        """, (limit,)).fetchall()
        return [
            {
                "id": r[0],
                "event_uuid": r[1],
                "event_type": r[2],
                "payload": json.loads(r[3]),
                "attempts": r[4]
            }
            for r in rows
        ]
    finally:
        conn.close()


def mark_outbox_synced(event_id):
    from datetime import datetime
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE outbox_events
            SET status = 'synced', synced_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), event_id))
        conn.commit()
    finally:
        conn.close()


def mark_outbox_failed(event_id, error):
    from datetime import datetime
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE outbox_events
            SET attempts = attempts + 1,
                last_error = ?,
                status = CASE WHEN attempts + 1 >= 10
                          THEN 'failed' ELSE 'pending' END
            WHERE id = ?
        """, (error, event_id))
        conn.commit()
    finally:
        conn.close()


def get_outbox_stats():
    conn = get_connection()
    try:
        cur = conn.cursor()
        rows = cur.execute("""
            SELECT status, COUNT(*) FROM outbox_events GROUP BY status
        """).fetchall()
        return {status: count for status, count in rows}
    finally:
        conn.close()


def insert_tag_reading(timestamp, tag_name, data_type, value):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO tag_readings (timestamp, tag_name, data_type, value)
        VALUES (?, ?, ?, ?)
    """, (timestamp, tag_name, data_type, str(value)))
    conn.commit()
    conn.close()


def insert_machine_state(timestamp, state, reason=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO machine_states (timestamp, state, reason)
        VALUES (?, ?, ?)
    """, (timestamp, state, reason))
    conn.commit()
    conn.close()


def get_last_machine_state():
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("""
        SELECT state, reason FROM machine_states
        ORDER BY id DESC LIMIT 1
    """).fetchone()
    conn.close()
    return row if row else (None, None)


def insert_state_transition(timestamp, from_state, to_state, reason=None, duration_sec=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO state_transitions (timestamp, from_state, to_state, reason, duration_sec)
        VALUES (?, ?, ?, ?, ?)
    """, (timestamp, from_state, to_state, reason, duration_sec))
    conn.commit()
    conn.close()


def open_downtime_event(start_time, machine_unit, reason=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO downtime_events (start_time, machine_unit, reason)
        VALUES (?, ?, ?)
    """, (start_time, machine_unit, reason))
    event_id = cur.lastrowid
    conn.commit()
    conn.close()
    return event_id


def close_downtime_event(event_id, end_time, duration_sec):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE downtime_events
        SET end_time = ?, duration_sec = ?
        WHERE id = ?
    """, (end_time, duration_sec, event_id))
    conn.commit()
    conn.close()


def get_open_downtime_event(machine_unit):
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("""
        SELECT id, start_time FROM downtime_events
        WHERE machine_unit = ? AND end_time IS NULL
        ORDER BY id DESC LIMIT 1
    """, (machine_unit,)).fetchone()
    conn.close()
    return row if row else None


def insert_reject_event(timestamp):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO reject_events (timestamp) VALUES (?)", (timestamp,))
    conn.commit()
    conn.close()


def get_reject_count_since(since_timestamp):
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("""
        SELECT COUNT(*) FROM reject_events
        WHERE timestamp >= ?
    """, (since_timestamp,)).fetchone()
    conn.close()
    return row[0] if row else 0


def set_config(key, value):
    from datetime import datetime
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO oee_config (key, value, updated_at)
        VALUES (?, ?, ?)
    """, (key, str(value), datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_config(key, default=None):
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("SELECT value FROM oee_config WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row[0] if row else default


def insert_oee_result(period_start, period_end, planned_time_min,
                      run_time_min, downtime_min, total_count, good_count,
                      reject_count, ideal_cycle_time_sec,
                      availability, performance, quality, oee):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO oee_results (
            period_start, period_end,
            planned_time_min, run_time_min, downtime_min,
            total_count, good_count, reject_count, ideal_cycle_time_sec,
            availability, performance, quality, oee
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        period_start, period_end,
        planned_time_min, run_time_min, downtime_min,
        total_count, good_count, reject_count, ideal_cycle_time_sec,
        availability, performance, quality, oee
    ))
    conn.commit()
    conn.close()


def get_latest_count(tag_name):
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("""
        SELECT value FROM tag_readings
        WHERE tag_name = ?
        ORDER BY id DESC LIMIT 1
    """, (tag_name,)).fetchone()
    conn.close()
    return int(row[0]) if row else 0