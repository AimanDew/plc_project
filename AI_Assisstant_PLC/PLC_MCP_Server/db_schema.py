import sqlite3
import os


DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "plc_tags.db"
)
DB_PATH = os.path.abspath(DB_PATH)


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_database(tag_map):

    conn = get_connection()
    cur = conn.cursor()


    # ==========================
    # TABLE 1: tags (metadata)
    # ==========================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            name        TEXT PRIMARY KEY,
            db          INTEGER,
            byte        INTEGER,
            bit         INTEGER,
            data_type   TEXT
        )
    """)

    # ==========================
    # TABLE 2: tag_readings (raw history)
    # ==========================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tag_readings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            tag_name    TEXT NOT NULL,
            data_type   TEXT NOT NULL,
            value       TEXT NOT NULL
        )
    """)

    # ==========================
    # TABLE 3: machine_states
    # ==========================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS machine_states (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            state       TEXT NOT NULL,
            reason      TEXT
        )
    """)

    # ==========================
    # TABLE 4: state_transitions
    # ==========================
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

    # ==========================
    # TABLE 5: downtime_events
    # ==========================
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

    # ==========================
    # TABLE 6: production_runs
    # ==========================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS production_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time      TEXT NOT NULL,
            end_time        TEXT,
            ok_count_start   INTEGER,
            ok_count_end     INTEGER,
            total_produced   INTEGER
        )
    """)

    # ==========================
    # TABLE 7: reject_events (NG Count workaround)
    # ==========================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reject_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL
        )
    """)

    # ==========================
    # TABLE 8: oee_config (key-value)
    # ==========================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS oee_config (
            key     TEXT PRIMARY KEY,
            value   TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # ==========================
    # TABLE 9: shifts
    # ==========================
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

    # ==========================
    # TABLE 10: downtime_reasons (lookup)
    # ==========================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS downtime_reasons (
            code        INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            category    TEXT NOT NULL
        )
    """)

    # ==========================
    # TABLE 11: oee_results
    # ==========================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS oee_results (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            period_start        TEXT NOT NULL,
            period_end          TEXT NOT NULL,
            shift_id            INTEGER,
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
            oee                 REAL,
            FOREIGN KEY (shift_id) REFERENCES shifts(id)
        )
    """)

    # ==========================
    # Populate tags table from tag_map
    # ==========================
    for name, info in tag_map["tags"].items():
        cur.execute("""
            INSERT OR REPLACE INTO tags (name, db, byte, bit, data_type)
            VALUES (?, ?, ?, ?, ?)
        """, (
            name,
            tag_map["db"],
            info["byte"],
            info.get("bit"),
            info["type"]
        ))

    conn.commit()
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


def insert_oee_result(period_start, period_end, shift_id, planned_time_min,
                      run_time_min, downtime_min, total_count, good_count,
                      reject_count, ideal_cycle_time_sec,
                      availability, performance, quality, oee):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO oee_results (
            period_start, period_end, shift_id,
            planned_time_min, run_time_min, downtime_min,
            total_count, good_count, reject_count, ideal_cycle_time_sec,
            availability, performance, quality, oee
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        period_start, period_end, shift_id,
        planned_time_min, run_time_min, downtime_min,
        total_count, good_count, reject_count, ideal_cycle_time_sec,
        availability, performance, quality, oee
    ))
    conn.commit()
    conn.close()


def get_latest_ok_count():
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("""
        SELECT value FROM tag_readings
        WHERE tag_name = 'OEE Out OK Count'
        ORDER BY id DESC LIMIT 1
    """).fetchone()
    conn.close()
    return int(row[0]) if row else 0