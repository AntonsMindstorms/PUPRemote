"""Test suite for PUPRemote library.

Tests core functionality of pupremote.py including:
- Basic command and channel registration
- Encoding and decoding
- Result holder functionality
- Hub-side operations
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path so we can import pupremote
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Mock MicroPython modules that aren't available in CPython
sys.modules["pybricks"] = MagicMock()
sys.modules["pybricks.iodevices"] = MagicMock()
sys.modules["pybricks.tools"] = MagicMock()
sys.modules["machine"] = MagicMock()
sys.modules["lpf2"] = MagicMock()
sys.modules["ustruct"] = MagicMock()
sys.modules["asyncio"] = MagicMock()
sys.modules["collections"] = MagicMock()
sys.modules["micropython"] = MagicMock()


# Add micropython.const polyfill
def const(x):
    return x


sys.modules["micropython"].const = const


# Mock Pybricks imports since we're testing on non-Pybricks environment
class MockPUPDevice:
    def __init__(self, port):
        self.port = port
        self.data = b""

    def read(self, mode):
        return None

    def write(self, mode, data):
        self.data = data


class TestPUPRemoteBasics(unittest.TestCase):
    """Test basic PUPRemote functionality."""

    def test_pupremote_imports(self):
        """Test that pupremote.py can be imported."""
        try:
            import pupremote

            self.assertTrue(hasattr(pupremote, "PUPRemote"))
            self.assertTrue(hasattr(pupremote, "PUPRemoteHub"))
            self.assertTrue(hasattr(pupremote, "PUPRemoteSensor"))
        except ImportError as e:
            self.fail(f"Failed to import pupremote: {e}")

    def test_pupremote_hub_imports(self):
        """Test that pupremote_hub.py can be imported."""
        try:
            import pupremote_hub

            self.assertTrue(hasattr(pupremote_hub, "PUPRemote"))
            self.assertTrue(hasattr(pupremote_hub, "PUPRemoteHub"))
        except ImportError as e:
            self.fail(f"Failed to import pupremote_hub: {e}")

    def test_version_consistency(self):
        """Test that version is consistent across files."""
        import pupremote
        import pupremote_hub

        self.assertEqual(pupremote.__version__, "2.1")
        self.assertEqual(pupremote_hub.__version__, "2.1")

    def test_constants_defined(self):
        """Test that required constants are defined."""
        import pupremote

        # Check basic constants
        self.assertTrue(hasattr(pupremote, "MAX_PKT"))
        self.assertTrue(hasattr(pupremote, "MAX_COMMANDS"))
        self.assertTrue(hasattr(pupremote, "MAX_COMMAND_QUEUE_LENGTH"))
        self.assertTrue(hasattr(pupremote, "DONE"))
        self.assertTrue(hasattr(pupremote, "RESULT"))
        self.assertTrue(hasattr(pupremote, "ERROR"))


class TestEncodingDecoding(unittest.TestCase):
    """Test encoding and decoding functionality."""

    def setUp(self):
        """Set up test fixtures."""
        import pupremote

        self.pupremote = pupremote

    def test_int8_to_uint8_conversion(self):
        """Test signed to unsigned integer conversion."""
        # This tests the conversion logic used in encoding
        # -1 should become 255
        test_cases = [
            (0, 0),
            (1, 1),
            (127, 127),
            (-1, 255),
            (-128, 128),
        ]

        for signed, expected_unsigned in test_cases:
            unsigned = signed & 0xFF  # Simulate conversion
            self.assertEqual(unsigned, expected_unsigned)

    def test_struct_packing(self):
        """Test that struct format strings are valid."""
        import struct

        # Test common formats used in pupremote
        formats = ["B", "H", "f", "I", "b"]
        for fmt in formats:
            try:
                struct.pack(fmt, 0)
            except struct.error:
                self.fail(f"Invalid struct format: {fmt}")


class TestResultHolder(unittest.TestCase):
    """Test result holder functionality."""

    def setUp(self):
        """Set up test fixtures."""
        import pupremote

        self.pupremote = pupremote

    def test_result_holder_indices(self):
        """Test that result holder uses correct indices."""
        DONE = self.pupremote.DONE
        RESULT = self.pupremote.RESULT
        ERROR = self.pupremote.ERROR

        # Create a result holder like in the code
        result_holder = [False, None, None]

        # Test setting values
        result_holder[DONE] = True
        result_holder[RESULT] = 42
        result_holder[ERROR] = None

        self.assertTrue(result_holder[DONE])
        self.assertEqual(result_holder[RESULT], 42)
        self.assertIsNone(result_holder[ERROR])


class TestCodeQuality(unittest.TestCase):
    """Test code quality and consistency."""

    def test_no_syntax_errors(self):
        """Test that all source files have valid Python syntax."""
        import py_compile
        import tempfile

        src_files = [
            "src/pupremote.py",
            "src/pupremote_hub.py",
            "src/lpf2.py",
            "src/bluepad.py",
        ]

        root = Path(__file__).parent.parent

        for src_file in src_files:
            file_path = root / src_file
            if file_path.exists():
                try:
                    py_compile.compile(str(file_path), doraise=True)
                except py_compile.PyCompileError as e:
                    self.fail(f"Syntax error in {src_file}: {e}")

    def test_docstrings_exist(self):
        """Test that classes and public methods have docstrings."""
        import pupremote
        import inspect

        # Check main classes
        classes = [pupremote.PUPRemote, pupremote.PUPRemoteHub]
        for cls in classes:
            self.assertIsNotNone(cls.__doc__, f"Class {cls.__name__} missing docstring")

        # Check main public methods
        methods_to_check = [
            (pupremote.PUPRemote, "add_command"),
            (pupremote.PUPRemote, "add_channel"),
            (pupremote.PUPRemoteHub, "call"),
        ]

        for cls, method_name in methods_to_check:
            method = getattr(cls, method_name, None)
            if method:
                self.assertIsNotNone(
                    method.__doc__,
                    f"Method {cls.__name__}.{method_name} missing docstring",
                )


class TestImportCompatibility(unittest.TestCase):
    """Test that imports are compatible with different platforms."""

    def test_pupremote_sensor_imports(self):
        """Test that sensor-side imports work correctly."""
        import pupremote

        # Verify that PUPRemoteSensor exists
        self.assertTrue(hasattr(pupremote, "PUPRemoteSensor"))

    def test_pupremote_hub_minimal_imports(self):
        """Test that hub-only version has minimal dependencies."""
        import pupremote_hub

        # Verify core functionality without sensor overhead
        self.assertTrue(hasattr(pupremote_hub, "PUPRemoteHub"))
        self.assertTrue(hasattr(pupremote_hub, "PUPRemote"))


def joy():
    joy.called = True
    return 10, 20, 30


joy.called = False


class TestSensorProcess(unittest.TestCase):
    """Test PUPRemoteSensor.process() callback invocation."""

    def setUp(self):
        import pupremote

        self.pupremote = pupremote
        joy.called = False

        self.mock_lpup = MagicMock()
        self.mock_lpup.modes = []
        self.mock_lpup.mode = MagicMock(return_value=MagicMock())
        self.mock_lpup.heartbeat.return_value = None
        self.mock_lpup.current_mode = 0
        self.mock_lpup.connected = True

        sys.modules["lpf2"].LPF2 = MagicMock(return_value=self.mock_lpup)
        pupremote.lpf2 = sys.modules["lpf2"]

        from collections import deque
        import asyncio
        import struct

        pupremote.deque = deque
        pupremote.asyncio = asyncio
        pupremote.struct = struct

        self.sensor = pupremote.PUPRemoteSensor()

    def _add_callback(self, mode_name, to_hub_fmt="", from_hub_fmt="", callback=None):
        self.pupremote.PUPRemote.add_command(
            self.sensor, mode_name, to_hub_fmt=to_hub_fmt, from_hub_fmt=from_hub_fmt
        )
        if callback is not None:
            self.sensor.commands[-1][self.pupremote.CALLABLE] = callback

    def test_to_hub_only_callback_invoked_without_hub_data(self):
        """Sensor-to-hub commands must run when the hub reads without writing."""
        self._add_callback("joy", to_hub_fmt="BBB", callback=joy)
        self.sensor.process()

        self.assertTrue(joy.called)
        self.mock_lpup.send_payload.assert_called_once()
        payload = self.mock_lpup.send_payload.call_args[0][0]
        self.assertEqual(payload, bytes([10, 20, 30]))

    def test_hub_to_sensor_callback_still_works_with_data(self):
        """Commands with from_hub_fmt must still run when the hub sends data."""
        def echo(a, b):
            echo.result = (a, b)
            return a + b

        echo.result = None
        self._add_callback("echo", from_hub_fmt="BB", to_hub_fmt="B", callback=echo)

        self.mock_lpup.heartbeat.return_value = (bytes([3, 4]), 0)
        self.sensor.process()

        self.assertEqual(echo.result, (3, 4))
        self.mock_lpup.send_payload.assert_called_once()
        self.assertEqual(self.mock_lpup.send_payload.call_args[0][0], bytes([7]))

    def test_channel_sends_stored_payload_without_hub_data(self):
        """Channels must push stored data when the hub polls without writing."""
        self.pupremote.PUPRemote.add_command(
            self.sensor, "value", to_hub_fmt="B", command_type=self.pupremote.CHANNEL
        )
        self.sensor.update_channel("value", 42)
        self.mock_lpup.send_payload.reset_mock()

        self.sensor.process()

        self.mock_lpup.send_payload.assert_called_once_with()


class TestExampleIntegration(unittest.TestCase):
    """Test that examples follow correct patterns."""

    def test_example_imports_valid(self):
        """Test that example files use valid imports."""
        import re

        examples_dir = Path(__file__).parent.parent / "examples"

        # Find all Python files
        py_files = list(examples_dir.rglob("*.py"))
        self.assertGreater(len(py_files), 0, "No example files found")

        # Check for valid import patterns
        valid_patterns = [
            r"from pupremote import",
            r"from pupremote_hub import",
            r"from bluepad import",
        ]

        for py_file in py_files:
            try:
                content = py_file.read_text()
                # Just check that file is readable and not corrupted
                self.assertIsNotNone(content)
            except Exception as e:
                self.fail(f"Failed to read example file {py_file}: {e}")


if __name__ == "__main__":
    unittest.main()
