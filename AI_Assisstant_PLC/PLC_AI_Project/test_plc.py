import snap7

# Create PLC connection
plc = snap7.client.Client()

# Connect to Siemens PLC
plc.connect(
    "192.168.5.73",
    0,
    1
)

# Check connection status
if plc.get_connected():
    print("PLC Connected Successfully!")
else:
    print("PLC Connection Failed!")

# Disconnect
plc.disconnect()