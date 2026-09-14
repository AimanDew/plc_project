import sys
sys.path.insert(0, r"C:\AI_Assisstant_PLC\PLC_MCP_Server")

from plc import PLC

plc = PLC()

if plc.connect():
    print("Connected to PLC")
    
    # Get CPU info
    try:
        cpu_info = plc.client.get_cpu_info()
        print(f"CPU Info: {cpu_info}")
    except Exception as e:
        print(f"CPU Info failed: {e}")
    
    # Get CPU state
    try:
        state = plc.client.get_cpu_state()
        print(f"CPU State: {state}")
    except Exception as e:
        print(f"CPU State failed: {e}")
    
    # Try more DB numbers
    for db_num in [6, 7, 8, 9, 10, 20, 50, 100]:
        try:
            data = plc.client.db_read(db_num, 0, 4)
            print(f"DB{db_num} EXISTS! First 4 bytes: {[hex(b) for b in data]}")
        except Exception as e:
            print(f"DB{db_num}: {e}")
    
    plc.disconnect()
else:
    print("Failed to connect to PLC")