import sys
import os
import json
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from plc import PLC
from db_schema import (
    init_database,
    insert_tag_reading,
    insert_machine_state,
    get_last_machine_state,
    insert_state_transition,
    open_downtime_event,
    close_downtime_event,
    get_open_downtime_event,
    insert_reject_event
)
from state_classifier import classify_state


TAG_MAP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tag_map.json")

POLL_INTERVAL_SEC = 1.0
RECONNECT_DELAY_SEC = 5.0
MACHINE_UNIT = "OEE"

REJECT_TAG = "OEE Out TL Reject"


def load_tag_map():
    with open(TAG_MAP_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class OEELogger:

    def __init__(self):

        self.plc = PLC()
        self.tag_map = load_tag_map()
        self.connected = False
        self.prev_tags = None
        self.prev_state = None
        self.state_change_time = None
        self.prev_reject = False
        self.downtime_event_id = None

        init_database(self.tag_map)
        print(f"[{datetime.now().isoformat()}] Database initialized")


    def connect(self):

        attempt = 0

        while True:

            attempt += 1

            print(f"[{datetime.now().isoformat()}] Connecting to PLC (attempt {attempt})...")

            if self.plc.connect():

                self.connected = True
                print(f"[{datetime.now().isoformat()}] PLC connected")
                return True

            print(f"[{datetime.now().isoformat()}] Connection failed, retrying in {RECONNECT_DELAY_SEC}s")
            time.sleep(RECONNECT_DELAY_SEC)


    def read_tags(self):

        try:

            return self.plc.read_all_tags()

        except Exception as e:

            print(f"[{datetime.now().isoformat()}] Read error: {e}")
            self.connected = False
            return None


    def poll_once(self):

        tags = self.read_tags()

        if tags is None or "Error" in tags:

            self.handle_disconnect()
            return

        if not self.connected:
            print(f"[{datetime.now().isoformat()}] PLC reconnected")
            self.connected = True

        now = datetime.now()
        ts = now.isoformat()

        # ==========================
        # 1. LOG CHANGED TAGS
        # ==========================
        changed = 0

        if self.prev_tags is None:
            for name, value in tags.items():
                dtype = self.tag_map["tags"][name]["type"]
                insert_tag_reading(ts, name, dtype, value)
                changed += 1
        else:
            for name, value in tags.items():
                if self.prev_tags.get(name) != value:
                    dtype = self.tag_map["tags"][name]["type"]
                    insert_tag_reading(ts, name, dtype, value)
                    changed += 1

        # ==========================
        # 2. REJECT TRANSITION COUNTING
        # ==========================
        current_reject = tags.get(REJECT_TAG, False)

        if self.prev_reject is not None and not self.prev_reject and current_reject:
            insert_reject_event(ts)
            print(f"[{ts}] Reject detected (transition)")

        self.prev_reject = current_reject

        # ==========================
        # 3. MACHINE STATE CLASSIFICATION
        # ==========================
        state, reason = classify_state(tags)

        if state != self.prev_state:

            duration = None

            if self.state_change_time is not None:
                duration = (now - self.state_change_time).total_seconds()

            insert_state_transition(ts, self.prev_state, state, reason, duration)

            if self.prev_state is not None:
                print(f"[{ts}] State: {self.prev_state} -> {state} (reason: {reason}, duration: {duration:.1f}s)")
            else:
                print(f"[{ts}] Initial state: {state} (reason: {reason})")

            # ==========================
            # 4. DOWNTIME EVENT TRACKING
            # ==========================
            if state == "DOWN":

                self.downtime_event_id = open_downtime_event(ts, MACHINE_UNIT, reason)
                print(f"[{ts}] Downtime started: {reason}")

            elif self.prev_state == "DOWN" and self.downtime_event_id is not None:

                start_row = get_open_downtime_event(MACHINE_UNIT)

                if start_row:
                    event_id, start_time = start_row
                    start_dt = datetime.fromisoformat(start_time)
                    dur = (now - start_dt).total_seconds()
                    close_downtime_event(event_id, ts, dur)
                    print(f"[{ts}] Downtime ended, duration: {dur:.1f}s")

                self.downtime_event_id = None

            self.prev_state = state
            self.state_change_time = now

        insert_machine_state(ts, state, reason)

        self.prev_tags = tags

        if changed > 0:
            print(f"[{ts}] {changed} tag(s) changed | state={state} | OK={tags.get('OEE Out OK Count', '?')}")


    def handle_disconnect(self):

        if self.connected:
            print(f"[{datetime.now().isoformat()}] PLC disconnected, attempting reconnect...")
            self.connected = False

        time.sleep(RECONNECT_DELAY_SEC)
        self.connect()


    def run(self):

        print(f"[{datetime.now().isoformat()}] OEE Logger starting")
        print(f"  Poll interval: {POLL_INTERVAL_SEC}s")
        print(f"  Machine unit: {MACHINE_UNIT}")
        print(f"  Reject tag: {REJECT_TAG}")
        print()

        self.connect()

        while True:

            try:

                self.poll_once()

            except KeyboardInterrupt:

                print(f"\n[{datetime.now().isoformat()}] Stopped by user")
                break

            except Exception as e:

                print(f"[{datetime.now().isoformat()}] Unexpected error: {e}")
                time.sleep(RECONNECT_DELAY_SEC)

            time.sleep(POLL_INTERVAL_SEC)

        self.plc.disconnect()
        print(f"[{datetime.now().isoformat()}] Disconnected. Goodbye.")


if __name__ == "__main__":

    logger = OEELogger()
    logger.run()