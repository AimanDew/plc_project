import sys
sys.path.insert(0, r"C:\AI_Assisstant_PLC\PLC_MCP_Server")

from plc import PLC

plc = PLC()

if plc.connect():
    print("Connected to PLC")
    
    # Test DB1 (should work - old project)
    print("\n--- Testing DB1 ---")
    try:
        data = plc.client.db_read(1, 0, 6)
        print(f"DB1 exists! Raw bytes: {[hex(b) for b in data]}")
    except Exception as e:
        print(f"DB1 error: {e}")
    
    # Test DB3 (new)
    print("\n--- Testing DB3 ---")
    for size in [6, 10, 20, 50]:
        try:
            data = plc.client.db_read(3, 0, size)
            print(f"DB3 exists! Size {size}: {[hex(b) for b in data]}")
            break
        except Exception as e:
            print(f"DB3 size {size}: {e}")
    
    # Try listing blocks (S7-1200/1500)
    print("\n--- Trying to list blocks ---")
    try:
        blocks = plc.client.list_blocks()
        print(f"Blocks: {blocks}")
    except Exception as e:
        print(f"List blocks failed: {e}")
    
    plc.disconnect()
else:
    print("Failed to connect to PLC")