import sys
import time
from datetime import datetime

sys.path.insert(0, r"C:\AI_Assisstant_PLC\PLC_MCP_Server")

from plc import PLC
from snap7.util import get_bool, set_bool


def scan_all_bits(plc, max_byte=19):
    """Read all booleans in DB3 and return only TRUE bits."""
    data = plc.client.db_read(3, 0, max_byte + 1)
    true_bits = []
    for byte in range(max_byte + 1):
        for bit in range(8):
            if get_bool(data, byte, bit):
                true_bits.append(f"{byte}.{bit}")
    return true_bits, data


plc = PLC()

if not plc.connect():
    print("PLC connection failed")
    sys.exit(1)

print(f"Connected at {datetime.now()}")
print(f"PLC IP: {plc.client.get_connected()}")

# Show current state before any writes
bits_before, data_before = scan_all_bits(plc)
print(f"\nInitial TRUE bits in DB3: {bits_before}")
print(f"Byte 6 before: 0x{data_before[6]:02X}")

# Set 6.4 = True and verify over time
mod = bytearray(data_before)
set_bool(mod, 6, 4, True)
plc.client.db_write(3, 0, bytes(mod))
print(f"\nWrote 6.4 = True at {datetime.now()}")

for i in range(10):
    time.sleep(1)
    bits, data = scan_all_bits(plc)
    print(f"[{datetime.now()}] TRUE bits: {bits} | Byte 6: 0x{data[6]:02X} | 6.4: {get_bool(data, 6, 4)}")

plc.disconnect()
print(f"\nDisconnected at {datetime.now()}")