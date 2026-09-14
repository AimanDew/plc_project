import snap7
from snap7.util import set_bool


# Create PLC connection
plc = snap7.client.Client()


# Connect PLC
plc.connect(
    "192.168.4.190",
    0,
    1
)


if plc.get_connected():

    print("PLC Connected Successfully!")

    # Read current DB3 data
    data = plc.db_read(3, 0, 20)


    # Change Enable DG (Byte 0, Bit 0)
    set_bool(data, 0, 0, True)

    # Change Enable OEE (Byte 0, Bit 1)
    set_bool(data, 0, 1, False)


    # Write data back to PLC
    plc.db_write(3, 0, data)


    print("Enable DG set to True")
    print("Enable OEE set to False")


else:
    print("PLC Connection Failed!")


plc.disconnect()