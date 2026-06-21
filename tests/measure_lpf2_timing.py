# Measure DCM + hub CMD_SPEED timing on LMS-ESP32 (one run per plug-in).
#
# Copy to the board or run from REPL after plug-in. Unplug/replug the PUP cable
# between sweeps if you change UART_DROP.
#
# Example:
#   from measure_lpf2_timing import sweep, measure_once
#   measure_once(uart_drop=19)   # single capture
#   sweep(17, 22)                # try drops 17..21 (replug each time!)

from lpf2 import LPF2, DATA8, HUB_CMD_SPEED
from lms_esp32 import RX_PIN, TX_PIN

MODE = LPF2.mode(
    "TEST",
    1,
    DATA8,
    format="3.0",
    symbol="T",
    raw_range=(0, 100),
    percent_range=(0, 100),
    si_range=(0, 100),
)

LISTEN_MS = 200


def measure_once(uart_drop=19, listen_ms=LISTEN_MS):
    lpf2 = LPF2([MODE], rx=RX_PIN, tx=TX_PIN, debug=False)
    print("--- measure uart_drop={} listen_ms={} ---".format(uart_drop, listen_ms))
    drops, buf, off = lpf2.measure_fast_probe(uart_drop, listen_ms)
    if off >= 0:
        print("RESULT: CMD_SPEED found at byte", off)
    else:
        print("RESULT: CMD_SPEED not found")
    return drops, buf, off


def sweep(first_drop=17, last_drop=22, listen_ms=LISTEN_MS):
    """Call measure_once(d) manually after each replug — no auto sweep on device."""
    print(
        "Call measure_once(d) after each replug, d in {}..{}".format(
            first_drop, last_drop
        )
    )


if __name__ == "__main__":
    measure_once(uart_drop=19)
