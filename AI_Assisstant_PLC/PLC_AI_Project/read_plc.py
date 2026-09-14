import snap7
from snap7.util import get_bool, get_int


# Create PLC connection
plc = snap7.client.Client()


# Connect PLC
plc.connect(
    "192.168.5.73",
    0,
    1
)


# Check connection
if plc.get_connected():

    print("PLC Connected Successfully!")

    # Read DB1 first 6 bytes
    data = plc.db_read(1, 0, 6)


    # Read Boolean values
    start = get_bool(data, 0, 0)
    stop = get_bool(data, 0, 1)
    motor = get_bool(data, 0, 2)


    # Read Integer values
    speed = get_int(data, 2)
    frequency = get_int(data, 4)


    print("---------------------")
    print("START :", start)
    print("STOP  :", stop)
    print("MOTOR :", motor)
    print("SPEED :", speed)
    print("FREQ  :", frequency)


else:
    print("PLC Connection Failed!")


plc.disconnect()