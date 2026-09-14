import sys
sys.path.insert(0, r"C:\AI_Assisstant\AI_Assisstant_PLC\PLC_MCP_Server")

from plc import PLC
from snap7.util import get_bool, get_int, get_real

plc = PLC()

if not plc.connect():
    sys.exit(1)

data = plc.client.db_read(3, 0, 28)

print("DB3 RAW DUMP (28 bytes):")
print("=" * 70)
for i in range(0, 28, 16):
    chunk = data[i:i+16]
    hex_part = " ".join(f"{b:02X}" for b in chunk)
    print(f"  {i:3d}: {hex_part}")

print()
print("DECODED VALUES (corrected offsets):")
print("=" * 70)

tags = [
    ("Enable DG",                     "bool", 0, 0),
    ("Enable OEE",                    "bool", 0, 1),
    ("[padding]",                     "byte", 1, None),
    ("Shared Inputs.DG.Auto / Man",   "bool", 2, 0),
    ("Shared Inputs.DG.E-Stop",       "bool", 2, 1),
    ("Shared Inputs.DG.On Peltier",   "bool", 2, 2),
    ("Shared Inputs.DG.On Small Fan", "bool", 2, 3),
    ("Shared Inputs.DG.On Large Fan", "bool", 2, 4),
    ("[padding byte 3]",              "byte", 3, None),
    ("Shared Inputs.OEE.Auto / Man",  "bool", 4, 0),
    ("Shared Inputs.OEE.E-Stop",      "bool", 4, 1),
    ("Shared Inputs.OEE.Stop",        "bool", 4, 2),
    ("Shared Inputs.OEE.Start",       "bool", 4, 3),
    ("Shared Inputs.OEE.Reset",       "bool", 4, 4),
    ("[padding byte 5]",              "byte", 5, None),
    ("DG Outputs.Peltier",            "bool", 6, 0),
    ("DG Outputs.Small Fan",          "bool", 6, 1),
    ("DG Outputs.Large Fan",          "bool", 6, 2),
    ("DG Outputs.LED Peltier",        "bool", 6, 3),
    ("DG Outputs.LED Small Fan",      "bool", 6, 4),
    ("DG Outputs.LED Large Fan",      "bool", 6, 5),
    ("DG Outputs.TL Error",           "bool", 6, 6),
    ("DG Outputs.TL Heating",         "bool", 6, 7),
    ("DG Outputs.TL Cooling",         "bool", 7, 0),
    ("DG Outputs.Machine OK",         "bool", 7, 1),
    ("DG Outputs.Machine ERR",        "bool", 7, 2),
    ("DG Outputs.Machine STAT",       "usint",8, None),
    ("[padding byte 9]",              "byte", 9, None),
    ("DG Outputs.Temp RD 0",          "real", 10, None),
    ("DG Outputs.Temp RD 1",          "real", 14, None),
    ("DG Outputs.Temp DIF",           "real", 18, None),
    ("OEE Outputs.Conveyor",          "bool", 22, 0),
    ("OEE Outputs.Speed",             "bool", 22, 1),
    ("OEE Outputs.Direction",         "bool", 22, 2),
    ("OEE Outputs.TL Error",          "bool", 22, 3),
    ("OEE Outputs.TL Reject",         "bool", 22, 4),
    ("OEE Outputs.TL Accept",         "bool", 22, 5),
    ("OEE Outputs.Machine OK",        "bool", 22, 6),
    ("OEE Outputs.Machine ERR",       "bool", 22, 7),
    ("OEE Outputs.Machine STAT",      "usint",23, None),
    ("OEE Outputs.Step ID",           "int",  24, None),
    ("OEE Outputs.OK Count",          "int",  26, None),
]

for name, dtype, byte_off, bit_off in tags:
    if "[padding" in name:
        val = data[byte_off]
        flag = "  <-- ZERO (padding)" if val == 0 else f"  <-- NON-ZERO: 0x{val:02X}"
        print(f"  {name:40s} byte {byte_off:2d} = 0x{val:02X}{flag}")
    elif dtype == "bool":
        val = get_bool(data, byte_off, bit_off)
        print(f"  {name:40s} {byte_off}.{bit_off} = {val}")
    elif dtype == "usint":
        val = data[byte_off]
        print(f"  {name:40s} byte {byte_off:2d} = {val} (0x{val:02X})")
    elif dtype == "int":
        val = get_int(data, byte_off)
        print(f"  {name:40s} byte {byte_off:2d} = {val}")
    elif dtype == "real":
        val = get_real(data, byte_off)
        print(f"  {name:40s} byte {byte_off:2d} = {val}")

print()
print("=" * 70)
print("IMPORTANT: DB3 is only 28 bytes (0-27)")
print("OEE Outputs.NG Count (Int, 2 bytes) does NOT fit in this DB!")
print("It would need bytes 28-29, which don't exist.")
print("Likely: NG Count was added in TIA Portal but not downloaded to PLC yet.")

plc.disconnect()