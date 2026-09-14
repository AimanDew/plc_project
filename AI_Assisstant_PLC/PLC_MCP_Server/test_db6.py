import sys
sys.path.insert(0, r"C:\AI_Assisstant_PLC\PLC_MCP_Server")

from plc import PLC

plc = PLC()

if plc.connect():
    print("Connected to PLC")
    
    # Read DB6 with different sizes
    for size in [4, 10, 20, 50, 100, 200]:
        try:
            data = plc.client.db_read(6, 0, size)
            print(f"DB6 size {size}: OK ({len(data)} bytes)")
            print(f"  First 20 bytes: {[hex(b) for b in data[:20]]}")
        except Exception as e:
            print(f"DB6 size {size}: {e}")
            break
    
    # Check DB2-5
    for db_num in [2, 3, 4, 5]:
        try:
            data = plc.client.db_read(db_num, 0, 4)
            print(f"DB{db_num} EXISTS! First 4 bytes: {[hex(b) for b in data]}")
        except Exception as e:
            print(f"DB{db_num}: {e}")
    
    plc.disconnect()
else:
    print("Failed to connect to PLC")