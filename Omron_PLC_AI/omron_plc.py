import socket
import struct
import json
import os


# ==========================
# PLC CONNECTION SETTINGS
# ==========================

TAG_MAP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tag_map.json")


def _load_config():
    with open(TAG_MAP_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# FINS memory area codes (per fins-driver library)
# Bit access vs Word access use different codes
FINS_AREAS = {
    # word access
    "D_WORD":   0x82,
    "W_WORD":   0xB1,
    "CIO_WORD": 0xB0,
    "H_WORD":   0xB2,
    "A_WORD":   0xB3,
    # bit access
    "D_BIT":    0x02,
    "W_BIT":    0x31,
    "CIO_BIT":  0x30,
    "H_BIT":    0x32,
    "A_BIT":    0x33,
}


# ==========================
# PLC CLASS
# ==========================

class OmronPLC:

    def __init__(self):

        config = _load_config()

        self.ip = config["plc_ip"]
        self.port = config["plc_port"]
        self.src_node = config["src_node"]
        self.dst_node = config["dst_node"]

        self.sock = None
        self.connected = False
        self.tag_map = config
        self._sid = 1


    # ==========================
    # CONNECT
    # ==========================

    def connect(self):

        try:

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(5)

            pc_ip = self.tag_map.get("pc_ip", "0.0.0.0")
            self.sock.bind((pc_ip, 0))

            # Test connection by reading D0
            data = self._fins_read("D0", 1)

            if data is not None:

                self.connected = True
                print("Omron PLC Connected")
                return True

            else:

                print("Omron PLC Connection Failed")
                return False

        except Exception as e:

            print("Omron PLC Connection Error:", e)
            return False


    # ==========================
    # DISCONNECT
    # ==========================

    def disconnect(self):

        if self.sock:

            self.sock.close()
            self.sock = None

        self.connected = False
        print("Omron PLC Disconnected")


    # ==========================
    # PARSE FINS ADDRESS
    # ==========================

    def _parse_address(self, address):

        bit = None

        if "." in address:
            addr_part, bit_str = address.rsplit(".", 1)
            bit = int(bit_str)
        else:
            addr_part = address

        area = ""
        word_str = ""
        for ch in addr_part:
            if ch.isalpha():
                area += ch
            else:
                word_str += ch

        word = int(word_str)
        area_upper = area.upper()

        if area_upper == "D":
            area_code = 0x02 if bit is not None else 0x82
        elif area_upper == "W":
            area_code = 0x31 if bit is not None else 0xB1
        elif area_upper == "CIO":
            area_code = 0x30 if bit is not None else 0xB0
        elif area_upper == "H":
            area_code = 0x32 if bit is not None else 0xB2
        elif area_upper == "A":
            area_code = 0x33 if bit is not None else 0xB3
        else:
            raise ValueError(f"Unknown memory area: {area}")

        return area_code, word, bit


    # ==========================
    # FINS READ
    # ==========================

    def _fins_read(self, address, num_items=1):

        area_code, word, bit = self._parse_address(address)

        bit_field = bit if bit is not None else 0x00

        # FINS command: MRC(2) + Area(1) + Word(2) + Bit(1) + Count(2) = 8 bytes
        command = bytes([
            0x01, 0x01,                              # MRC: Memory Area Read
            area_code,                               # Memory area code
            (word >> 8) & 0xFF, word & 0xFF,          # Word address (big-endian)
            bit_field,                               # Bit address
            (num_items >> 8) & 0xFF, num_items & 0xFF # Count
        ])

        response = self._send_fins(command)

        if response is None:
            return None

        # Response: header(10) + MRC(2) + EndCode(2) + Data
        if len(response) < 14:
            print(f"Short response: {response.hex()}")
            return None

        end_code = int.from_bytes(response[12:14], "big")

        if end_code != 0x0000:
            print(f"FINS read error: 0x{end_code:04x} for {address}")
            return None

        return response[14:]


    # ==========================
    # FINS WRITE
    # ==========================

    def _fins_write(self, address, data_bytes):

        area_code, word, bit = self._parse_address(address)

        bit_field = bit if bit is not None else 0x00

        # FINS command: MRC(2) + Area(1) + Word(2) + Bit(1) + Count(2) + Data
        command = bytes([
            0x01, 0x02,                              # MRC: Memory Area Write
            area_code,                               # Memory area code
            (word >> 8) & 0xFF, word & 0xFF,          # Word address
            bit_field,                               # Bit address
            (len(data_bytes) >> 8) & 0xFF, len(data_bytes) & 0xFF
        ]) + data_bytes

        response = self._send_fins(command)

        if response is None:
            return False

        if len(response) < 14:
            return False

        end_code = int.from_bytes(response[12:14], "big")

        if end_code != 0x0000:
            print(f"FINS write error: 0x{end_code:04x} for {address}")
            return False

        return True


    # ==========================
    # SEND FINS PACKET
    # ==========================

    def _send_fins(self, command):

        if not self.sock:
            print("Not connected")
            return None

        # FINS/UDP header (10 bytes):
        # ICF(1) + RSV(1) + GCT(1) + DNA(1) + DA1(1) + DA2(1) + SNA(1) + SA1(1) + SA2(1) + SID(1)
        header = bytes([
            0x80,                    # ICF: request
            0x00,                    # RSV
            0x02,                    # GCT
            0x00,                    # DNA: dest network
            self.dst_node,           # DA1: dest node (PLC)
            0x00,                    # DA2: dest unit
            0x00,                    # SNA: source network
            self.src_node,           # SA1: source node (PC)
            0x00,                    # SA2: source unit
            self._sid,               # SID
        ])

        self._sid = (self._sid + 1) & 0xFF
        if self._sid == 0:
            self._sid = 1

        packet = header + command

        try:
            self.sock.sendto(packet, (self.ip, self.port))
            data, addr = self.sock.recvfrom(2048)
            return data
        except socket.timeout:
            print("FINS timeout")
            self.connected = False
            return None
        except Exception as e:
            print("FINS send error:", e)
            self.connected = False
            return None


    # ==========================
    # READ TAG BY NAME
    # ==========================

    def read_tag(self, name):

        if name not in self.tag_map["tags"]:
            return {"Error": f"Tag '{name}' not found"}

        info = self.tag_map["tags"][name]
        address = info["address"]
        dtype = info["type"]

        try:
            if dtype == "bool":
                data = self._fins_read(address, 1)
                if data is None:
                    return {"Error": "Read failed"}
                value = data[0] != 0

            elif dtype == "int":
                data = self._fins_read(address, 1)
                if data is None:
                    return {"Error": "Read failed"}
                value = int.from_bytes(data[:2], "big", signed=True)

            elif dtype == "dint":
                data = self._fins_read(address, 2)
                if data is None:
                    return {"Error": "Read failed"}
                value = int.from_bytes(data[:4], "big", signed=True)

            elif dtype == "real":
                data = self._fins_read(address, 2)
                if data is None:
                    return {"Error": "Read failed"}
                value = struct.unpack(">f", data[:4])[0]

            else:
                return {"Error": f"Unsupported type: {dtype}"}

            return {
                "name": name,
                "address": address,
                "type": dtype,
                "value": value
            }

        except Exception as e:
            return {"Error": str(e)}


    # ==========================
    # READ ALL TAGS
    # ==========================

    def read_all_tags(self):

        results = {}

        for name in self.tag_map["tags"]:
            result = self.read_tag(name)
            if "Error" in result:
                results[name] = None
            else:
                results[name] = result["value"]

        return results


    # ==========================
    # WRITE TAG BY NAME
    # ==========================

    def write_tag(self, name, value):

        if name not in self.tag_map["tags"]:
            return {"Error": f"Tag '{name}' not found"}

        info = self.tag_map["tags"][name]
        address = info["address"]
        dtype = info["type"]

        try:
            if dtype == "bool":
                if isinstance(value, str):
                    value = value.lower() in ("true", "1", "on")
                data = bytes([0x01 if value else 0x00])
                success = self._fins_write(address, data)

            elif dtype == "int":
                data = int(value).to_bytes(2, "big", signed=True)
                success = self._fins_write(address, data)

            elif dtype == "dint":
                data = int(value).to_bytes(4, "big", signed=True)
                success = self._fins_write(address, data)

            elif dtype == "real":
                data = struct.pack(">f", float(value))
                success = self._fins_write(address, data)

            else:
                return {"Error": f"Unsupported type: {dtype}"}

            if success:
                return {
                    "name": name,
                    "address": address,
                    "type": dtype,
                    "value": value,
                    "status": "written"
                }
            else:
                return {"Error": "Write failed"}

        except Exception as e:
            return {"Error": str(e)}


    # ==========================
    # LIST TAGS
    # ==========================

    def list_tags(self):

        tags = []

        for name, info in self.tag_map["tags"].items():
            tags.append({
                "name": name,
                "address": info["address"],
                "type": info["type"],
                "comment": info.get("comment", "")
            })

        return tags