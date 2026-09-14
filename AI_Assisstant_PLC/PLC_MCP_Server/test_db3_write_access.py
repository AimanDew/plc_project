import sys
sys.path.insert(0, r"C:\AI_Assisstant_PLC\PLC_MCP_Server")
import time
from plc import PLC
from snap7.util import set_bool

plc = PLC()

if plc.connect():
    print("Connected to PLC")
    
    # Read original state
    original = plc.client.db_read(3, 0, 20)
    print(f"Original: {[hex(b) for b in original]}")
    
    # Test writing 0xAA to each byte one at a time
    for byte_offset in range(20):
        data = bytearray(original)
        data[byte_offset] = 0xAA
        
        plc.client.db_write(3, 0, bytes(data))
        time.sleep(0.3)
        
        verify = plc.client.db_read(3, 0, 20)
        changed = verify[byte_offset] == 0xAA
        print(f"Byte {byte_offset:02d}: wrote 0xAA, read back 0x{verify[byte_offset]:02X}, persisted={changed}")
    
    print("\nFinal state:")
    final = plc.client.db_read(3, 0, 20)
    print([hex(b) for b in final])
    
    plc.disconnect()
else:
    print("Failed to connect")