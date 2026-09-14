import sys
sys.path.insert(0, r"C:\AI_Assisstant\AI_Assisstant_PLC\PLC_MCP_Server")

from plc import PLC

plc = PLC()

if not plc.connect():
    print("Failed to connect")
    sys.exit(1)

print("Connected. Testing DB3 read sizes:\n")

for size in [1, 4, 8, 10, 20, 28, 32, 40, 64]:
    try:
        data = plc.client.db_read(3, 0, size)
        print(f"  Size {size:3d}: OK -> {[hex(b) for b in data]}")
    except Exception as e:
        print(f"  Size {size:3d}: FAIL -> {e}")
        break

print("\nAlso checking DB1 (for comparison):")
try:
    data = plc.client.db_read(1, 0, 6)
    print(f"  DB1 size 6: OK -> {[hex(b) for b in data]}")
except Exception as e:
    print(f"  DB1: FAIL -> {e}")

plc.disconnect()
print("\nDisconnected.")