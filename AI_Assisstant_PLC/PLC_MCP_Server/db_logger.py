import sys
import os
import json
import sqlite3
from datetime import datetime

sys.path.insert(0, r"C:\AI_Assisstant\AI_Assisstant_PLC\PLC_MCP_Server")

from plc import PLC


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plc_tags.db")
DB_PATH = os.path.abspath(DB_PATH)

TAG_MAP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tag_map.json")


def create_database(db_path):

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            name        TEXT PRIMARY KEY,
            db          INTEGER,
            byte        INTEGER,
            bit         INTEGER,
            data_type   TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tag_readings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            tag_name    TEXT NOT NULL,
            data_type   TEXT NOT NULL,
            value       TEXT NOT NULL,
            FOREIGN KEY (tag_name) REFERENCES tags(name)
        )
    """)

    conn.commit()
    conn.close()

    print(f"Database created at: {db_path}")


def populate_tag_metadata(db_path, tag_map_path):

    with open(tag_map_path, "r", encoding="utf-8") as f:
        tag_map = json.load(f)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

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

    print(f"Tag metadata populated: {len(tag_map['tags'])} tags")


def snapshot_all_tags(db_path):

    plc = PLC()

    if not plc.connect():
        print("Failed to connect to PLC")
        return False

    all_tags = plc.read_all_tags()

    plc.disconnect()

    if "Error" in all_tags:
        print(f"Error reading tags: {all_tags}")
        return False

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    timestamp = datetime.now().isoformat()

    for name, value in all_tags.items():

        cur.execute("""
            INSERT INTO tag_readings (timestamp, tag_name, data_type, value)
            VALUES (?, ?, ?, ?)
        """, (
            timestamp,
            name,
            cur.execute("SELECT data_type FROM tags WHERE name = ?", (name,)).fetchone()[0],
            str(value)
        ))

    conn.commit()
    conn.close()

    print(f"Snapshot saved at {timestamp} ({len(all_tags)} tags)")
    return True


def print_database(db_path):

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print("\n" + "=" * 70)
    print("TAGS TABLE (metadata)")
    print("=" * 70)
    print(f"{'Name':<30} {'DB':<4} {'Byte':<5} {'Bit':<4} {'Type'}")
    print("-" * 70)

    for row in cur.execute("SELECT name, db, byte, bit, data_type FROM tags ORDER BY byte, bit"):
        name, db, byte, bit, dtype = row
        bit_str = str(bit) if bit is not None else "-"
        print(f"{name:<30} {db:<4} {byte:<5} {bit_str:<4} {dtype}")

    print("\n" + "=" * 70)
    print("TAG READINGS (latest snapshot)")
    print("=" * 70)
    print(f"{'Name':<30} {'Type':<8} {'Value':<15} {'Timestamp'}")
    print("-" * 70)

    for row in cur.execute("""
        SELECT tag_name, data_type, value, timestamp
        FROM tag_readings
        WHERE id IN (SELECT MAX(id) FROM tag_readings GROUP BY tag_name)
        ORDER BY timestamp DESC, tag_name
    """):
        name, dtype, value, ts = row
        print(f"{name:<30} {dtype:<8} {value:<15} {ts}")

    conn.close()


def main():

    print("Creating database...")
    create_database(DB_PATH)

    print("\nPopulating tag metadata from tag_map.json...")
    populate_tag_metadata(DB_PATH, TAG_MAP_PATH)

    print("\nTaking snapshot from live PLC...")
    success = snapshot_all_tags(DB_PATH)

    if success:
        print_database(DB_PATH)
    else:
        print("\nSnapshot failed - showing metadata only")
        print_database(DB_PATH)

    print(f"\nDatabase location: {DB_PATH}")


if __name__ == "__main__":
    main()