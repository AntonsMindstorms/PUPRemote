# Trimmed version of pupremote that only runs on Pybricks hubs
# Includes async/multitask support for concurrent hub-side operations
#
# This is a lightweight version (44% smaller than pupremote.py) optimized for:
# - Pybricks block code:
#      - import sync functions connect(), add_command(), call()
#      - import async functions call_multitask(), process_async()
# - Pybricks multitask support for concurrent operations
# - Low memory footprint on Pybricks hubs
# - Hub-side only (no sensor emulation code)
# - Async support via call_multitask() and process_async()
# - Compatible with Pybricks multitask for concurrent operations

__author__ = "Anton Vanhoucke & Ste7an"
__copyright__ = "Copyright 2023,2024 AntonsMindstorms.com"
__license__ = "GPL"
__version__ = "2.1"
__status__ = "Production"

import ustruct as struct
from pybricks.iodevices import PUPDevice
from pybricks.tools import wait, run_task
from micropython import const

MAX_PKT = const(16)

# Result holder indices
DONE = const(0)
RESULT = const(1)
ERROR = const(2)

# Dictionary keys
NAME = const(0)
SIZE = const(1)
TO_HUB_FORMAT = const(2)
FROM_HUB_FORMAT = const(3)
ARGS_TO_HUB = const(5)
ARGS_FROM_HUB = const(6)
CALLBACK = const(0)
CHANNEL = const(1)


def connect(port):
    """
    Connect to LMS-ESP32. Pass Port as a string ('A') or a number (1=Port.A)
    """
    global pr
    if isinstance(port, str):
        pyport = eval("Port." + port)
    if isinstance(port, int):
        pyport = eval("Port." + chr(64 + port))
    pr = PUPRemoteHub(pyport)


def call(*args):
    try:
        return pr.call(*args)
    except:
        print("Use the connect & add_channel or add_command blocks before call")
        raise


def add_channel(name, encoding):
    try:
        pr.add_channel(name, encoding)
    except:
        print("Use the connect command before adding a channel")
        raise


def add_command(name, to_hub, from_hub):
    try:
        pr.add_command(name, to_hub_fmt=to_hub, from_hub_fmt=from_hub)
    except:
        print("Use the connect command before adding a command")
        raise


def call_multitask(*args, **kwargs):
    try:
        return pr.call_multitask(*args, **kwargs)
    except:
        print(
            "Use the connect & add_channel or add_command blocks before call_multitask"
        )
        raise


def process_async():
    try:
        return pr.process_async()
    except:
        print("Use the connect command before starting process_async")
        raise


class PUPRemote:
    """Base class for PUPRemoteHub on Pybricks.

    Defines a list of commands and their formats. Contains encoding/decoding
    functions for communication between hub and sensor.

    Args:
        max_packet_size: Maximum packet size in bytes, defaults to 16 for Pybricks compatibility.
    """

    def __init__(self, max_packet_size=MAX_PKT):
        self.commands = []
        self.modes = {}
        self.max_packet_size = max_packet_size

    def add_channel(self, mode_name: str, to_hub_fmt: str = ""):
        """Define a data channel to read on the hub.

        Use this function with identical parameters on both the sensor and the hub.
        You can call a channel like a command, but to update the data on the sensor
        side, you need to `update_channel(<name>, *args)`.

        Args:
            mode_name: The name of the mode you defined on the sensor side.
            to_hub_fmt: The format string of the data sent from the sensor to the hub.
                Use 'repr' to receive any python object. Or use a struct format string.
                See https://docs.python.org/3/library/struct.html
        """
        self.add_command(mode_name, to_hub_fmt=to_hub_fmt, command_type=CHANNEL)

    def add_command(
        self,
        mode_name: str,
        to_hub_fmt: str = "",
        from_hub_fmt: str = "",
        command_type=CALLBACK,
    ):
        """Define a remote call.

        Use this function with identical parameters on both the sensor and the hub.

        Args:
            mode_name: The name of the mode you defined on the sensor side.
            to_hub_fmt: The format string of the data sent from the sensor to the hub.
                Use 'repr' to receive any python object. Or use a struct format string.
                See https://docs.python.org/3/library/struct.html
            from_hub_fmt: The format string of the data sent from the hub.
            command_type: CALLBACK or CHANNEL (internal).
        """
        if to_hub_fmt == "repr" or from_hub_fmt == "repr":
            msg_size = self.max_packet_size
            num_args_from_hub = -1
            num_args_to_hub = -1
        else:
            size_to_hub_fmt = struct.calcsize(to_hub_fmt)
            size_from_hub_fmt = struct.calcsize(from_hub_fmt)
            msg_size = max(size_to_hub_fmt, size_from_hub_fmt)
            num_args_to_hub = len(
                struct.unpack(to_hub_fmt, bytearray(struct.calcsize(to_hub_fmt)))
            )
            num_args_from_hub = len(
                struct.unpack(from_hub_fmt, bytearray(struct.calcsize(from_hub_fmt)))
            )

        assert msg_size <= self.max_packet_size, "Payload exceeds maximum packet size"
        self.commands.append(
            {
                NAME: mode_name,
                TO_HUB_FORMAT: to_hub_fmt,
                SIZE: msg_size,
                ARGS_TO_HUB: num_args_to_hub,
            }
        )
        if command_type == CALLBACK:
            self.commands[-1][FROM_HUB_FORMAT] = from_hub_fmt
            self.commands[-1][ARGS_FROM_HUB] = num_args_from_hub

        # Build a dictionary of mode names and their index
        self.modes[mode_name] = len(self.commands) - 1

    def decode(self, fmt: str, data: bytes):
        if fmt == "repr":
            clean = data.rstrip(b"\x00")
            return (eval(clean),) if clean else ("",)
        else:
            size = struct.calcsize(fmt)
            data = struct.unpack(fmt, data[:size])
        return data

    def encode(self, size, format, *argv):
        if format == "repr":
            s = bytes(repr(*argv), "UTF-8")
        else:
            s = struct.pack(format, *argv)
        assert len(s) <= size, "Payload exceeds maximum packet size"
        return s


class PUPRemoteHub(PUPRemote):
    """Communicate with a PUPRemoteSensor from a Pybricks hub.

    Use on the hub side running Pybricks. Copy the commands you defined on the sensor
    side to the hub side using add_command() and add_channel().

    Args:
        port: The port to which the PUPRemoteSensor is connected (e.g., Port.A).
        max_packet_size: Set to 16 for Pybricks compatibility, defaults to 32.
    """

    def _int8_to_uint8(self, arr):
        return [((i + 128) & 0xFF) - 128 for i in arr]

    def __init__(self, port, max_packet_size=MAX_PKT):
        super().__init__(max_packet_size)
        self.port = port
        try:
            self.pup_device = PUPDevice(port)
        except OSError:
            self.pup_device = None
            print("Check wiring and remote script. Unable to connect on ", self.port)
            raise
        # Multitask stuff
        self._queue = []
        self._multitask_loop_running = False

    def add_command(
        self, mode_name, to_hub_fmt="", from_hub_fmt="", command_type=CALLBACK
    ):
        super().add_command(mode_name, to_hub_fmt, from_hub_fmt, command_type)
        # Check the newly added commands against the advertised modes.
        modes = self.pup_device.info()["modes"]
        n = len(self.commands) - 1  # Zero indexed mode number
        assert len(self.commands) <= len(modes), "More commands than on remote side"
        assert (
            mode_name == modes[n][0].rstrip()
        ), "Expected '{}' as mode {}, but got '{}'".format(
            modes[n][0].rstrip(), n, mode_name
        )
        assert (
            self.commands[-1][SIZE] == modes[n][1]
        ), "Different parameter size than on remote side. Check formats."

    def call(self, mode_name: str, *argv, wait_ms=0) -> object:
        """Call a remote function on the sensor side.

        Args:
            mode_name: The name of the mode you defined on both sides.
            *argv: Arguments to pass to the remote function.
            wait_ms: Time to wait before reading after sending (optional).
                Defaults to 0ms. A good value is `struct.calcsize(from_hub_fmt) * 1.5` (ms)

        Returns:
            The return value from the remote function, or a tuple of values.

        Raises:
            AssertionError: If called during a multitask operation.
        """
        assert (
            not run_task()
        ), "Use 'call_multitask' instead of 'call', with multiple start blocks or multitask blocks"

        mode = self.modes[mode_name]
        size = self.commands[mode][SIZE]

        if FROM_HUB_FORMAT in self.commands[mode]:
            num_args = self.commands[mode][ARGS_FROM_HUB]
            if num_args >= 0:
                assert (
                    len(argv) == num_args
                ), "Expected {} argument(s) in call '{}'".format(num_args, mode_name)
            self.pup_device.read(mode)
            payl = self.encode(size, self.commands[mode][FROM_HUB_FORMAT], *argv)
            self.pup_device.write(
                mode,
                [
                    ((i + 128) & 0xFF) - 128
                    for i in tuple(payl + b"\x00" * (size - len(payl)))
                ],
            )
            wait(wait_ms)

        data = self.pup_device.read(mode)
        raw_data = bytes([b if b>=0 else b+256 for b in data])
        result = self.decode(self.commands[mode][TO_HUB_FORMAT], raw_data)
        # Convert tuple size 1 to single value
        return result[0] if len(result) == 1 else result

    async def call_multitask(self, command_name: str, *argv, wait_ms=0):
        """Call a remote function asynchronously for use with Pybricks multitask.

        Make sure to run process_async() as a separate task before using this.

        Args:
            command_name: The name of the command.
            *argv: Arguments to pass to the remote function.
            wait_ms: Time to wait before reading after sending. Defaults to 0ms.

        Returns:
            The return value from the remote function, or a tuple of values.
        """
        if not self._multitask_loop_running:
            raise AssertionError(
                "Start 'process_async' as a seperate task (coroutine) before using 'call_multitask()'"
            )

        result_holder = [False, None, None]  # [done, result, error]
        self._queue.append((command_name, argv, wait_ms, result_holder))

        while not result_holder[DONE]:
            await wait(1)  # cooperative multitasking

        if result_holder[ERROR]:
            raise result_holder[ERROR]
        return result_holder[RESULT]

    async def _execute_call(self, mode_name: str, *argv, wait_ms=0):
        mode = self.modes[mode_name]
        size = self.commands[mode][SIZE]

        if FROM_HUB_FORMAT in self.commands[mode]:
            num_args = self.commands[mode][ARGS_FROM_HUB]
            if num_args >= 0:
                assert len(argv) == num_args, "Args mismatch in {}".format(mode_name)
            await self.pup_device.read(mode)
            payl = self.encode(size, self.commands[mode][FROM_HUB_FORMAT], *argv)
            await self.pup_device.write(
                mode,
                [
                    ((i + 128) & 0xFF) - 128
                    for i in tuple(payl + b"\x00" * (size - len(payl)))
                ],
            )
            await wait(wait_ms)

        data = await self.pup_device.read(mode)
        raw_data = bytes([b if b>=0 else b+256 for b in data])
        result = self.decode(self.commands[mode][TO_HUB_FORMAT], raw_data)
        # Convert tuple size 1 to single value
        return result[0] if len(result) == 1 else result

    async def process_async(self):
        """
        Process multitask MicroPUP calls in a queue to avoid EAGAIN or IOERR.
        """
        self._multitask_loop_running = True
        running = False
        while True:
            if self._queue and not running:
                running = True
                command_name, argv, wait_ms, result_holder = self._queue.pop(0)

                try:
                    result = await self._execute_call(
                        command_name, *argv, wait_ms=wait_ms
                    )
                    result_holder[RESULT] = result
                except Exception as e:
                    result_holder[ERROR] = e
                    print(e)
                    raise
                finally:
                    result_holder[DONE] = True
                    running = False
            await wait(1)
