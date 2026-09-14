import snap7
import json
import os
from snap7.util import get_bool, get_int, set_bool, set_int, get_real, set_real, get_usint, set_usint


# ==========================
# PLC CONNECTION SETTINGS
# ==========================

PLC_IP = "192.168.4.190"
RACK = 0
SLOT = 1


# ==========================
# PLC CLASS
# ==========================

class PLC:

    def __init__(self):

        self.client = snap7.client.Client()


    # ==========================
    # CONNECT PLC
    # ==========================

    def connect(self):

        try:

            self.client.connect(
                PLC_IP,
                RACK,
                SLOT
            )


            if self.client.get_connected():

                print("PLC Connected")
                return True

            else:

                print("PLC Connection Failed")
                return False


        except Exception as e:

            print("PLC Connection Error:", e)
            return False



    # ==========================
    # READ DB3 (TEST)
    # ==========================

    def read_db3_raw(self, size=64):
        try:
            data = self.client.db_read(3, 0, size)
            return {"raw_bytes": [hex(b) for b in data], "length": len(data)}
        except Exception as e:
            return {"Error": str(e)}


    # ==========================
    # TAG MAP LOADING
    # ==========================

    def _load_tag_map(self):

        tag_map_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "tag_map.json"
        )

        try:

            with open(tag_map_path, "r", encoding="utf-8") as f:

                tag_map = json.load(f)

            return tag_map

        except Exception as e:

            print("Failed to load tag_map.json:", e)

            return None


    # ==========================
    # LIST ALL TAGS
    # ==========================

    def list_tags(self):

        tag_map = self._load_tag_map()

        if not tag_map:

            return {"Error": "tag_map.json not found or invalid"}

        tags = []

        for name, info in tag_map["tags"].items():

            entry = {
                "name": name,
                "db": tag_map["db"],
                "byte": info["byte"],
                "type": info["type"]
            }

            if "bit" in info:

                entry["bit"] = info["bit"]

            tags.append(entry)

        return tags


    # ==========================
    # READ TAG BY NAME
    # ==========================

    def read_tag(self, name):

        tag_map = self._load_tag_map()

        if not tag_map:

            return {"Error": "tag_map.json not found or invalid"}

        if name not in tag_map["tags"]:

            return {"Error": f"Tag '{name}' not found in tag map"}

        info = tag_map["tags"][name]

        db = tag_map["db"]

        byte = info["byte"]

        dtype = info["type"]


        try:

            if dtype == "bool":

                data = self.client.db_read(db, byte, 1)

                value = get_bool(data, 0, info["bit"])

            elif dtype == "usint":

                data = self.client.db_read(db, byte, 1)

                value = data[0]

            elif dtype == "int":

                data = self.client.db_read(db, byte, 2)

                value = get_int(data, 0)

            elif dtype == "real":

                data = self.client.db_read(db, byte, 4)

                value = get_real(data, 0)

            else:

                return {"Error": f"Unsupported type '{dtype}'"}

            return {
                "name": name,
                "db": db,
                "byte": byte,
                "type": dtype,
                "value": value
            }

        except Exception as e:

            return {"Error": str(e)}


    # ==========================
    # READ ALL TAGS
    # ==========================

    def read_all_tags(self):

        tag_map = self._load_tag_map()

        if not tag_map:

            return {"Error": "tag_map.json not found or invalid"}

        db = tag_map["db"]

        size = tag_map["size"]

        results = {}


        try:

            data = self.client.db_read(db, 0, size)

        except Exception as e:

            return {"Error": f"Failed to read DB{db}: {e}"}


        for name, info in tag_map["tags"].items():

            byte = info["byte"]

            dtype = info["type"]

            try:

                if dtype == "bool":

                    value = get_bool(data, byte, info["bit"])

                elif dtype == "usint":

                    value = data[byte]

                elif dtype == "int":

                    value = get_int(data, byte)

                elif dtype == "real":

                    value = get_real(data, byte)

                else:

                    value = None

                results[name] = value

            except Exception as e:

                results[name] = f"Error: {e}"

        return results


    # ==========================
    # WRITE TAG BY NAME
    # ==========================

    def write_tag(self, name, value):

        tag_map = self._load_tag_map()

        if not tag_map:

            return {"Error": "tag_map.json not found or invalid"}

        if name not in tag_map["tags"]:

            return {"Error": f"Tag '{name}' not found in tag map"}

        info = tag_map["tags"][name]

        db = tag_map["db"]

        byte = info["byte"]

        dtype = info["type"]


        try:

            if dtype == "bool":

                if isinstance(value, str):

                    value = value.lower() in ("true", "1", "on")

                data = self.client.db_read(db, byte, 1)

                set_bool(data, 0, info["bit"], bool(value))

                self.client.db_write(db, byte, data)

            elif dtype == "usint":

                data = self.client.db_read(db, byte, 1)

                data[0] = int(value) & 0xFF

                self.client.db_write(db, byte, data)

            elif dtype == "int":

                data = self.client.db_read(db, byte, 2)

                set_int(data, 0, int(value))

                self.client.db_write(db, byte, data)

            elif dtype == "real":

                data = self.client.db_read(db, byte, 4)

                set_real(data, 0, float(value))

                self.client.db_write(db, byte, data)

            else:

                return {"Error": f"Unsupported type '{dtype}'"}

            return {
                "name": name,
                "db": db,
                "byte": byte,
                "type": dtype,
                "value": value,
                "status": "written"
            }

        except Exception as e:

            return {"Error": str(e)}


    # ==========================
    # DISCONNECT PLC
    # ==========================

    def disconnect(self):

        try:

            self.client.disconnect()

            print("PLC Disconnected")


        except Exception as e:

            print(e)