import sys
sys.path.insert(0, r"C:\AI_Assisstant_PLC\PLC_MCP_Server")

from plc import PLC

plc = PLC()
# IP already updated in plc.py to 192.168.4.190

if plc.connect():
    print("Connected to PLC")
    
    # Try reading DB3 with different sizes
    for size in [6, 10, 20, 50, 100]:
        result = plc.read_db3_raw(size)
        print(f"\nDB3 read (size={size}): {result}")
        if "Error" not in result:
            print(f"  Success! DB3 exists and has at least {size} bytes")
            break
    
    plc.disconnect()
else:
    print("Failed to connect to PLC")