# Minimal test to check if lpf2.connect() works on LMS-ESP32

from lpf2 import LPF2, DATA8
from lms_esp32 import RX_PIN, TX_PIN
import time

my_mode = LPF2.mode("TEST", 1, DATA8, format="3.0", symbol="T", raw_range=(0, 100), percent_range=(0, 100), si_range=(0, 100))
lpf2 = LPF2([my_mode], rx=RX_PIN, tx=TX_PIN, debug=True)
lpf2.connect()
time.sleep(1)
print(lpf2.connected)