# Copy this to LMS-ESP32 via Viper-IDE.
# Ensure LMS-ESP32 is flashed with MicroPython 1.27 or newer (20251228 or later) via firmware.antonsmindstorms.com.
# Copy hotrod_rc.py to the LEGO Inventor Hub (or SPIKE hub) after flashing it with pybricks.
# Then download the BlueMote app on your phone and connect to the ESP32 to control the HotRod car.


from btbricks import RCReceiver
from pupremote import PUPRemoteSensor

rc = RCReceiver()
p = PUPRemoteSensor(power=True)
p.add_channel('rc', to_hub_fmt="bbh") # 2 bytes for each stick, 1 byte for the triggers and trims, and 1 byte for the buttons. Total 5 bytes.

while True:
    if rc.is_connected():
        lx, ly, rx, ry, ltrigger, rtrigger, ltrim, rtrim, btns = rc.controller_state()
        p.update_channel('rc', ly, rx, rtrim)
    else:
        p.update_channel('rc', 0, 0, 0)
    p.process()