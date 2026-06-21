# RX-only listen experiment — one run per plug-in on LMS-ESP32.
#
# Verifies: can we skip GPIO DCM and find hub CMD_SPEED (0x52…) by listening
# @115200 with tx=-1 and sensor TX held low?
#
# Run immediately after plugging into the hub (or from main.py on boot):
#   import experiment_rx_only_listen
#   experiment_rx_only_listen.run()
#
# Compare with GPIO DCM log from measure_lpf2_timing.measure_once().

from lpf2 import LPF2, DATA8, CONNECT_DCM_MS
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

LISTEN_MS = CONNECT_DCM_MS  # 450 ms — full DCM window


def run(listen_ms=LISTEN_MS):
    print("=== experiment_rx_only_listen listen_ms={} ===".format(listen_ms))
    lpf2 = LPF2([MODE], rx=RX_PIN, tx=TX_PIN, debug=False)
    buf, hist, off = lpf2.experiment_rx_only_listen(listen_ms)
    if off >= 0:
        print("RESULT: CMD_SPEED found — RX-only path may work")
    else:
        print("RESULT: CMD_SPEED not found — check histogram above")
    return buf, hist, off


if __name__ == "__main__":
    run()
