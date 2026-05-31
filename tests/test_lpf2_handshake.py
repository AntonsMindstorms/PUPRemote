import importlib
import sys
import types
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class _FakeTime:
    def __init__(self):
        self._ticks = 0

    def sleep_ms(self, ms):
        self._ticks += max(ms, 0)

    def ticks_ms(self):
        return self._ticks


def _ensure_mock_modules():
    if "machine" not in sys.modules:
        machine = types.ModuleType("machine")

        class DummyPin:
            IN = 0
            OUT = 1
            PULL_DOWN = 2

            def __init__(self, *args, **kwargs):
                self._value = 0

            def value(self, v=None):
                if v is None:
                    return self._value
                self._value = v

        class DummyUart:
            def __init__(self, *args, **kwargs):
                pass

            def any(self):
                return 0

            def read(self, _):
                return None

            def write(self, _):
                return 0

        machine.Pin = DummyPin
        machine.UART = DummyUart
        sys.modules["machine"] = machine

    if "utime" not in sys.modules:
        utime = types.ModuleType("utime")
        utime.sleep_ms = lambda _ms: None
        utime.ticks_ms = lambda: 0
        sys.modules["utime"] = utime


class TestLPF2Handshake(unittest.TestCase):
    def setUp(self):
        _ensure_mock_modules()
        sys.modules.pop("lpf2", None)
        self.lpf2 = importlib.reload(importlib.import_module("lpf2"))
        self.lpf2.implementation = ("cpython", 0, "")
        self.fake_time = _FakeTime()
        self.lpf2.utime = self.fake_time
        mode = [
            "M0",
            [1, self.lpf2.DATA8, 3, 0],
            [0, 100],
            [0, 100],
            [0, 100],
            "",
            [self.lpf2.ABSOLUTE, self.lpf2.ABSOLUTE],
            True,
            1,
            0,
        ]
        self.sensor = self.lpf2.LPF2([mode], rx=18, tx=19, uart_n=2)

    def test_read_cmd_speed_parses_valid_frame(self):
        payload = (115200).to_bytes(4, "little")
        frame = bytearray([self.lpf2.CMD_Baud]) + payload
        frame.append(self.sensor.calc_cksm(frame))
        stream = iter([0x99] + list(frame))
        self.sensor.readchar = lambda: next(stream, -1)

        self.assertEqual(self.sensor._read_cmd_speed(timeout_ms=10), 115200)

    def test_sync_fast_uart_requires_115200(self):
        writes = []
        self.sensor.fast_uart = lambda: None
        self.sensor.write = lambda data: writes.append(bytes(data))

        self.sensor._read_cmd_speed = lambda timeout_ms=50: 115200
        self.assertTrue(self.sensor._sync_fast_uart_with_host())
        self.assertEqual(writes, [bytes([self.lpf2.BYTE_ACK])])

        writes.clear()
        self.sensor._read_cmd_speed = lambda timeout_ms=50: 2400
        self.assertFalse(self.sensor._sync_fast_uart_with_host())
        self.assertEqual(writes, [])

    def test_connect_fallback_uses_slow_sync_without_raw_zero(self):
        writes = []
        calls = {"slow": 0, "fast": 0}

        self.sensor.init_pins = lambda: None
        self.sensor.wrt_tx_pin = lambda *_: None
        self.sensor._sync_fast_uart_with_host = lambda: False
        self.sensor._emit_sync_info_messages = lambda: None
        self.sensor.slow_uart = lambda: calls.__setitem__("slow", calls["slow"] + 1)
        self.sensor.fast_uart = lambda: calls.__setitem__("fast", calls["fast"] + 1)
        self.sensor.readchar = lambda: self.lpf2.BYTE_ACK
        self.sensor.write = lambda data: writes.append(bytes(data))

        self.sensor.connect()

        self.assertTrue(self.sensor.connected)
        self.assertEqual(calls["slow"], 1)
        self.assertEqual(calls["fast"], 1)  # Switch to advertised 115200 after sync ACK.
        self.assertNotIn(b"\x00", writes)
        self.assertIn(bytes([self.lpf2.BYTE_ACK]), writes)


if __name__ == "__main__":
    unittest.main()
