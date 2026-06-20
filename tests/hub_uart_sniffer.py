# Pybricks hub script — raw UART sniffer on a port (run while ESP32 connects).
# Expect CMD_SPEED probe: 0x52 0x00 0xc2 0x01 0x00 0x6e at 115200 after plug-in.

from pybricks.iodevices import UARTDevice
from pybricks.parameters import Port
from pybricks.tools import StopWatch, wait

PORT = Port.A  # change to your port
DURATION_MS = 5000
POLL_MS = 50

uart = UARTDevice(PORT, baudrate=115200)
print("Sniffing", PORT, "at 115200 for", DURATION_MS, "ms")
sw = StopWatch()
while sw.time() < DURATION_MS:
    data = uart.read(32)
    if data:
        print(" ".join(hex(b) for b in data))
    wait(POLL_MS)

print("done")
