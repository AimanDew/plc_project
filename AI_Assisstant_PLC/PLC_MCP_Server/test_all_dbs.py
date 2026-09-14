import sys
sys.path.insert(0, r"C:\AI_Assisstant_PLC\PLC_MCP_Server")

from plc import PLC

plc = PLC()

if plc.connect():
    print("Connected to PLC")
    
    # Try multiple DB numbers
    for db_num in range(1, 20):
        try:
            data = plc.client.db_read(db_num, 0, 4)
            print(f"DB{db_num} EXISTS! First 4 bytes: {[hex(b) for b in data]}")
        except Exception as e:
            if "Invalid address" not in str(e):
                print(f"DB{db_num}: {e}")
    
    plc.disconnect()
else:
    print("Failed to connect to PLC")