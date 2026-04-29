from pybricks.hubs import InventorHub
from pybricks.pupdevices import Motor, ColorSensor, UltrasonicSensor
from pybricks.parameters import Button, Color, Direction, Port, Side, Stop
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch
from pupremote_hub import PUPRemoteHub

hub = InventorHub()
pr = PUPRemoteHub(Port.D) # Check if LMS-ESP32 is connected to Port D on the hub!
pr.add_channel('rc', "bbh") # 2 bytes for each stick and 1 byte for the trims. Total 5 bytes.
steer = Motor(Port.A)
drive = Motor(Port.B)

while 1:
    vals = pr.call('rc')
    print(vals)
    drive.dc(vals[0]*-1)
    steer.track_target(vals[1]*-1)