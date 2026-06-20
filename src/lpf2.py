# LPF2 class allows communication between LEGO SPIKE Prime and third party devices.
__author__ = "Anton Vanhoucke & Ste7an"
__copyright__ = "Copyright 2023, 2024 AntonsMindstorms.com"
__license__ = "GPL"
__version__ = "2.1"
__status__ = "Production"

import machine
import struct
import utime
try:
    from micropython import const
except ImportError:
    def const(i):
        return i
    
from sys import implementation

# OpenMV board platform type
# sys.implementation[2]: OPENMV4P-STM32H743
OPENMV = const(0)
# LMS-ESP32 board platform type
# sys.implementation[2]: ESP32 module (lvgl,ulab,spiram) with ESP32
ESP32 = const(1)
# OpenMV RT board platform type
# sys.implementation[2]: OpenMV IMXRT1060-MIMXRT1062DVJ6A
OPENMVRT = const(2)
# OpenMV AE3 board platform type
# sys.implementation[2]: OpenMV-AE3 with AE302F80F55D5AE
OPENMVAE3 = const(3)

MAX_PKT = const(32)

BYTE_NACK = const(0x02)
BYTE_ACK = const(0x04)
CMD_Type = const(0x40)  # @, set sensor type command
CMD_Select = const(0x43)  #  C, sets modes on the fly
CMD_MODES = const(0x41)  # I, set mode type command
CMD_EXT_MODE = const(0x46)
CMD_Baud = const(0x52)  # R, set the transmission baud rate
CMD_Vers = const(0x5F)  # _,  set the version number
MSG_INFO = const(0x80)  # name command
MSG_DATA = const(0xC0)  # data command
MSG_EXT_MODE = const(0x46)
EXT_MODE_0 = const(0x00)
EXT_MODE_8 = const(0x08)  # only used for extended mode > 7
CMD_LLL_SHIFT = const(3)
MSG_INFO_PLUS8 = const(0x20)

LEN_4 = const(2 << CMD_LLL_SHIFT)
LEN_2 = const(1 << CMD_LLL_SHIFT)
LEN_8 = const(3 << CMD_LLL_SHIFT)

NAME = const(0x0)
RAW = const(0x1)
PCT = const(0x2)
SI = const(0x3)
SYM = const(0x4)
FUNCTION_MAP = const(0x5)
FMT = const(0x80)

DATA8 = const(0)
DATA16 = const(1)
DATA32 = const(2)
DATAF = const(3)

# Input/Output Mapping flags, can be combined with |
WITH_NULL = const(2**7)  # Supports NULL value
FUNC_2 = const(2**6)  # Supports Functional Mapping 2.0+
ABSOLUTE = const(16)  # ABS (Absolute [min..max])
RELATIVE = const(8)  # REL (Relative [-1..1])
DISCRETE = const(4)  # DIS (Discrete [0, 1, 2, 3])

STRUCT_FMT = ("B", "H", "I", "f")

HEARTBEAT_PERIOD = const(1000)  # time of inactivity after which we reset sensor
MODE_GAP_MS = const(20)  # delay between mode info blocks at 2400 during connect
CONNECT_DCM_MS = const(450)  # total GPIO DCM window before registration
CONNECT_ACK_MS = const(2500)


def __num_bits(x):
    # Return the number of bits required to represent x
    n = 0
    while x > 0:
        x >>= 1
        n += 1
    return n


class LPF2(object):
    def __init__(
        self,
        modes,
        sensor_id=62,
        debug=False,
        max_packet_size=MAX_PKT,
        rx=None,
        tx=None,
        uart_n=None,
    ):
        self.modes = modes
        self.current_mode = 0
        self.sensor_id = sensor_id
        self.connected = False
        self.payloads = {}
        self.last_nack = 0
        self.debug = debug
        self.max_packet_size = max_packet_size
        self._debug_connect = False
        self.UART_N = uart_n
        self.TX_PIN_N = tx
        self.RX_PIN_N = rx
        if "RT1060" in implementation[2]:
            self.BOARD = OPENMVRT
            if uart_n == None:
                self.UART_N = 1
            print("OpenMV RT defaults loaded")
        elif "OPENMV4" in implementation[2]:
            self.BOARD = OPENMV
            import pyb
            self.pyb = pyb
            if uart_n == None:
                self.UART_N = 3
            print("OpenMV H7 defaults loaded")
        elif "OpenMV-AE3" in implementation[2]:
            self.BOARD = OPENMVAE3
            if uart_n == None:
                self.UART_N = 5
            print("OpenMV AE3 defaults loaded")
        else:
            self.BOARD = ESP32
            try:
                from lms_esp32 import RX_PIN,TX_PIN
            except ImportError:
                RX_PIN = 18
                TX_PIN = 19
            if tx == None:
                self.TX_PIN_N = TX_PIN
            if rx == None:
                self.RX_PIN_N = RX_PIN
            if uart_n == None:
                self.UART_N = 2
            print(
                "LMS-ESP32 defaults loaded, with rx={}, tx={}".format(self.RX_PIN_N, self.TX_PIN_N)
            )

    @staticmethod
    def mode(
        name,
        size=1,
        data_type=DATA8,
        writable=0,  # Leaving this for bw compatibility
        format="3.0",
        raw_range=[0, 100],
        percent_range=[0, 100],
        si_range=[0, 100],
        symbol="",
        functionmap=[ABSOLUTE, ABSOLUTE],  # [in (to hub), out (from hub)]
        view=True,
    ):
        fig, dec = format.split(".")
        total_data_size = size * 2**data_type  # Byte size of data set.
        # Find the power of 2 that is greater than the length of the data
        # -1 because of the header byte.
        bit_size = __num_bits(total_data_size - 1)
        mode_list = [
            name,  # 0
            [size, data_type, int(fig), int(dec)],  # 1
            raw_range,  # 2
            percent_range,  # 3
            si_range,  # 4
            symbol,  # 5
            functionmap,  # 6
            view and functionmap[0],  # 7
            total_data_size,  # 8
            bit_size,  # 9
        ]
        return mode_list

    def init_pins(self):
        if self.BOARD == ESP32:
            self.rx_pin = machine.Pin(self.RX_PIN_N, machine.Pin.IN)
            self.tx_pin = machine.Pin(
                self.TX_PIN_N, machine.Pin.OUT, machine.Pin.PULL_DOWN
            )
        elif self.BOARD == OPENMVRT:
            self.rx_pin = machine.Pin("P5", machine.Pin.IN)
            self.tx_pin = machine.Pin("P4", machine.Pin.OUT, machine.Pin.PULL_DOWN)
        elif self.BOARD == OPENMV:
            self.rx_pin = self.pyb.Pin("P5", self.pyb.Pin.IN)
            self.tx_pin = self.pyb.Pin("P4", self.pyb.Pin.OUT_PP)
        elif self.BOARD == OPENMVAE3:
            self.rx_pin = machine.Pin("P3", machine.Pin.IN)
            self.tx_pin = machine.Pin("P2", machine.Pin.OUT, machine.Pin.PULL_DOWN)

    def wrt_tx_pin(self, val, wait):
        # Reinit pin to deal with cable unplugging and re-plugging
        self.tx_pin.value(val)
        utime.sleep_ms(wait)

    def slow_uart(self):
        if self.BOARD == ESP32:
            self.uart = machine.UART(
                self.UART_N,
                baudrate=2400,
                rx=self.RX_PIN_N,
                tx=self.TX_PIN_N,
            )
        elif self.BOARD == OPENMVRT:
            self.uart = machine.UART(self.UART_N, 2400)
        elif self.BOARD == OPENMV:
            self.uart = self.pyb.UART(self.UART_N, 2400)
        elif self.BOARD == OPENMVAE3:
            self.uart = machine.UART(self.UART_N, 2400)

    def fast_uart(self):
        if self.BOARD == ESP32:
            self.uart = machine.UART(
                self.UART_N,
                baudrate=115200,
                rx=self.RX_PIN_N,
                tx=self.TX_PIN_N,
            )
        elif self.BOARD == OPENMVRT:
            self.uart = machine.UART(self.UART_N, 115200)
            utime.sleep_ms(5)
        elif self.BOARD == OPENMV:
            self.uart = self.pyb.UART(self.UART_N, 115200)
        elif self.BOARD == OPENMVAE3:
            self.uart = machine.UART(self.UART_N, 115200)
            utime.sleep_ms(5)

    # -------- Payload definition

    def load_payload(self, data, mode=None):
        if mode is None:
            mode = self.current_mode
        data_type = self.modes[mode][1][1]
        if isinstance(data, bytes):
            bin_data = data
        elif isinstance(data, bytearray):
            bin_data = data
        elif isinstance(data, list):
            # We have a list of integers. Pack them as bytes.
            bin_data = struct.pack("%d" % len(data) + STRUCT_FMT[data_type], *data)
        elif isinstance(data, float) or isinstance(data, int):
            bin_data = struct.pack(STRUCT_FMT[data_type], data)
        elif isinstance(data, str):
            # String. Convert to bytes of max size.
            bin_data = bytes(data, "UTF-8")[: self.max_packet_size]
        else:
            raise ValueError("Wrong data type: %s" % type(data))

        bytesize = self.modes[mode][8]
        bit = self.modes[mode][9]

        assert len(bin_data) > 0, "Payload is empty"
        assert len(bin_data) <= bytesize, "Wrong payload size"

        payload = bytearray(2**bit + 5)
        payload[0] = MSG_EXT_MODE
        payload[1] = EXT_MODE_0 if mode < 8 else EXT_MODE_8
        payload[2] = 0xFF ^ payload[0] ^ payload[1]
        cksm = 0xFF
        payload[3] = MSG_DATA | (bit << CMD_LLL_SHIFT) | (mode & 7)
        cksm ^= payload[3]
        for i in range(len(bin_data)):
            payload[i + 4] = bin_data[i]
            cksm ^= bin_data[i]
        payload[-1] = cksm  # No need to checksum zero bytes.

        self.payloads[mode] = payload

    def send_payload(self, data=None, mode=None):
        """
        Convert bytes of data to a proper LPF2 payload,
        save it to the payload of the current mode,
        and write it to the hub. If there is no data, just
        send current payload.
        """
        if not self.connected:
            if self.debug:
                print("Write payload, but not connected.")
            return
        if mode == None:
            mode = self.current_mode
        if data != None:
            self.load_payload(data, mode)
        self.write(self.payloads[mode])

    def update_payload(self, data, mode):
        if mode == self.current_mode:
            self.send_payload(data, mode)
        else:
            self.load_payload(data, mode)

    # ----- comm stuff

    def flush(self):
        if hasattr(self, "uart") and self.uart and self.uart.any():
            return self.uart.read(self.uart.any())

    @staticmethod
    def _byte_label(b):
        if b == 0x00:
            return "SYNC"
        if b == BYTE_NACK:
            return "NACK"
        if b == BYTE_ACK:
            return "ACK"
        if b == CMD_Baud:
            return "CMD_SPEED"
        if b == 0xF0:
            return "0xF0?"
        return hex(b)

    @staticmethod
    def _info_type_label(info_type):
        base = info_type & ~MSG_INFO_PLUS8
        plus = "+8" if info_type & MSG_INFO_PLUS8 else ""
        labels = {
            NAME: "NAME",
            RAW: "RAW",
            PCT: "PCT",
            SI: "SI",
            SYM: "SYM",
            FUNCTION_MAP: "MAP",
            FMT: "FMT",
        }
        return labels.get(base, hex(base)) + plus

    @staticmethod
    def _info_detail(array):
        if len(array) < 3:
            return ""
        info_type = array[1] & ~MSG_INFO_PLUS8
        if info_type in (NAME, SYM):
            s = bytes(array[2:-1]).split(b"\x00")[0]
            try:
                return '"{}"'.format(s.decode())
            except UnicodeError:
                return LPF2.str_b(s)
        if info_type in (RAW, PCT, SI) and len(array) >= 10:
            mn, mx = struct.unpack("<ff", bytes(array[2:10]))
            return "[{}, {}]".format(mn, mx)
        if info_type == FUNCTION_MAP and len(array) >= 5:
            return "in={} out={}".format(array[2], array[3])
        if info_type == FMT and len(array) >= 7:
            return "sz={} type={} fmt={}.{}".format(
                array[2], array[3], array[4], array[5]
            )
        return ""

    @staticmethod
    def _tx_label(array):
        if not array:
            return "empty"
        if len(array) == 1:
            if array[0] == 0x00:
                return "SYNC"
            if array[0] == BYTE_ACK:
                return "ACK"
        if array[0] == CMD_Type and len(array) >= 2:
            return "CMD_TYPE id={}".format(array[1])
        if array[0] == (CMD_MODES | LEN_4):
            return "CMD_MODES"
        if array[0] == CMD_Baud:
            return "CMD_SPEED"
        if array[0] == CMD_Vers:
            return "CMD_VERSION"
        if array[0] & 0xC0 == MSG_INFO and len(array) >= 2:
            mode = array[0] & 7
            if array[1] & MSG_INFO_PLUS8:
                mode += 8
            kind = LPF2._info_type_label(array[1])
            detail = LPF2._info_detail(array)
            if detail:
                return "MSG_INFO mode={} {} {}".format(mode, kind, detail)
            return "MSG_INFO mode={} {}".format(mode, kind)
        return "msg"

    def readchar(self, wait_ms=1):
        if self.uart.any():
            c = self.uart.read(1)
        elif wait_ms:
            utime.sleep_ms(wait_ms)
            if self.uart.any():
                c = self.uart.read(1)
            else:
                return -1
        else:
            return -1
        if c == None:
            return -1
        return ord(c)

    def heartbeat(self):
        if not self.connected:
            print("Checking heartbeat, but not connected. Initializing.")
            self.connect()
            return

        if utime.ticks_diff(utime.ticks_ms(), self.last_nack) > HEARTBEAT_PERIOD:
            print("Checking heartbeat, but line is dead. Re-initializing.")
            self.connected = False
            self.connect()
            return

        b = self.readchar(0)
        if b > 0:
            if b == BYTE_NACK:
                self.last_nack = utime.ticks_ms()
                self.send_payload()

            elif b == CMD_Select:
                self.last_nack = utime.ticks_ms()
                mode = self.readchar(1)
                cksm = self.readchar(1)
                if cksm == 0xFF ^ CMD_Select ^ mode:
                    self.current_mode = mode
                    self.send_payload()
                    if self.debug:
                        print("mode switch:", mode)

            elif b == CMD_EXT_MODE:
                self.last_nack = utime.ticks_ms()
                ext_mode = self.readchar(1)
                cksm = self.readchar(1)

                if cksm == 0xFF ^ CMD_EXT_MODE ^ ext_mode:
                    b = self.readchar(1)

                    size = 2 ** ((b & 0b111000) >> 3)

                    wrt_mode = (b & 0b111) + ext_mode

                    ck = 0xFF ^ b

                    buf = bytearray(size)
                    for i in range(size):
                        buf[i] = self.readchar(1)
                        ck ^= buf[i]

                    if ck == self.readchar(1):
                        return buf, wrt_mode
                    else:
                        print(
                            "Checksum error. Try reducing max_packet_size to 16 if using Pybricks."
                        )
            else:
                if self.debug:
                    buf = self.flush()
                    extra = self.str_b(buf) if buf else ""
                    print("unhandled rx", hex(b), extra)

    @staticmethod
    def str_b(b):
        if not b:
            return ""
        return " ".join(hex(c) for c in b)

    def write(self, array):
        if self.debug and self._debug_connect:
            print("tx", self._tx_label(array))
        return self.uart.write(array)

    @staticmethod
    def calc_cksm(array):
        chksm = 0xFF
        for b in array:
            chksm ^= b
        return chksm

    def addChksm(self, array):
        return array + self.calc_cksm(array).to_bytes(1, "little")

    # ---- settup definitions

    def setType(self, sensorType):
        return self.addChksm(bytearray([CMD_Type, sensorType]))

    def defineBaud(self, baud):
        rate = baud.to_bytes(4, "little")
        return self.addChksm(bytearray([CMD_Baud]) + rate)

    @staticmethod
    def str_vers_to_4_bytes(str_vers: str) -> bytes:
        stvb = bytes([int(n)&0xFF for n in str_vers.split(".")])
        if len(stvb) >= 4:
            return stvb[:4]
        return b"\x00" * (4 - len(stvb)) + stvb

    def defineVers(self, hardware: str, software: str):
        return self.addChksm(
            bytearray([CMD_Vers])
            + self.str_vers_to_4_bytes(hardware)
            + self.str_vers_to_4_bytes(software)
        )

    def str_info(self, data, num, info_type):
        if isinstance(data, str):  # Convert and truncate
            dt = bytearray(data, "UTF-8")[: self.max_packet_size]
        else:  # Bytes, or bytearray. Just truncate.
            dt = bytearray(data)[: self.max_packet_size]
        exp = __num_bits(len(dt) - 1)
        pl = bytearray(2**exp)
        pl[: len(dt)] = dt
        return self.addChksm(
            bytearray([MSG_INFO | exp << CMD_LLL_SHIFT | num, info_type]) + pl
        )

    def buildFunctMap(self, fmap, num, info_type):
        return self.addChksm(
            bytearray([MSG_INFO | LEN_2 | num, info_type, fmap[0], fmap[1]])
        )

    def buildFormat(self, fmt, num, info_type):
        sampleSize = fmt[0] & 0xFF
        dataType = fmt[1] & 0xFF
        figures = fmt[2] & 0xFF
        decimals = fmt[3] & 0xFF
        return self.addChksm(
            bytearray(
                [
                    MSG_INFO | LEN_4 | num,
                    info_type,
                    sampleSize,
                    dataType,
                    figures,
                    decimals,
                ]
            )
        )

    def buildRange(self, settings, num, rangeType):
        exp = 3 << CMD_LLL_SHIFT
        minVal = struct.pack("<f", settings[0])
        maxVal = struct.pack("<f", settings[1])
        return self.addChksm(
            bytearray([MSG_INFO | exp | num, rangeType]) + minVal + maxVal
        )

    def defineModes(self):
        n_modes = len(self.modes) - 1
        n_view_modes = sum(1 for m in self.modes if m[7])
        if n_view_modes:
            n_views = n_view_modes - 1
        else:
            n_views = n_modes
        n_views = max(0, n_views)
        return self.addChksm(
            bytearray(
                [
                    CMD_MODES | LEN_4,
                    min(n_modes, 7),
                    min(n_views, 7),
                    n_modes,
                    n_views,
                ]
            )
        )

    def setupMode(self, mode, num):
        self.load_payload(b"\x00" * mode[8], num)
        plus_8 = 0x00
        if num > 7:
            num -= 8
            plus_8 = MSG_INFO_PLUS8
        self.write(self.str_info(mode[0], num, NAME | plus_8))
        self.write(self.buildRange(mode[2], num, RAW | plus_8))
        self.write(self.buildRange(mode[3], num, PCT | plus_8))
        self.write(self.buildRange(mode[4], num, SI | plus_8))
        self.write(self.str_info(mode[5], num, SYM | plus_8))
        self.write(self.buildFunctMap(mode[6], num, FUNCTION_MAP | plus_8))
        self.write(self.buildFormat(mode[1], num, FMT | plus_8))

    def _send_info_sequence(self):
        self.write(self.setType(self.sensor_id))
        self.write(self.defineModes())
        self.write(self.defineBaud(115200))
        self.write(self.defineVers("0.1", __version__))
        num = len(self.modes) - 1
        for mode in reversed(self.modes):
            utime.sleep_ms(MODE_GAP_MS)
            self.setupMode(mode, num)
            num -= 1
        self.write(b"\x04")

    def _wait_hub_ack(self, timeout_ms=CONNECT_ACK_MS):
        t0 = utime.ticks_ms()
        deadline = utime.ticks_add(t0, timeout_ms)
        rx_hist = {}
        while utime.ticks_diff(deadline, utime.ticks_ms()) > 0:
            b = self.readchar(1)
            if b < 0:
                continue
            if self.debug and self._debug_connect:
                rx_hist[b] = rx_hist.get(b, 0) + 1
            if b == BYTE_ACK:
                self.connected = True
                if self.debug and self._debug_connect:
                    print(
                        "connect: hub ACK after {}ms".format(
                            utime.ticks_diff(utime.ticks_ms(), t0)
                        )
                    )
                return True
        if self.debug and self._debug_connect and rx_hist:
            parts = []
            for k in sorted(rx_hist.keys()):
                parts.append("{}x {}".format(rx_hist[k], self._byte_label(k)))
            print(
                "connect: no ACK in {}ms ({})".format(
                    timeout_ms, ", ".join(parts)
                )
            )
        return False

    def connect(self):
        assert len(self.modes) > 0, "No modes (commands) defined"
        self.connected = False
        self._debug_connect = self.debug
        self.init_pins()
        self.wrt_tx_pin(1, 5)
        self.wrt_tx_pin(0, 0)
        start = utime.ticks_ms()
        for i in range(24):
            if utime.ticks_diff(utime.ticks_ms(), start) >= CONNECT_DCM_MS:
                break
            n = 0
            while self.rx_pin.value() == 1:
                utime.sleep_ms(1)
                if n > 20:
                    break
                n += 1
            if self.debug:
                print("dcm drop {}: high {}ms".format(i, n))
            while self.rx_pin.value() == 0:
                utime.sleep_ms(1)
        sync_elapsed = utime.ticks_diff(utime.ticks_ms(), start)
        if self.debug:
            print("connect: dcm {}ms reg=slow@2400".format(sync_elapsed))
        self.slow_uart()
        remaining = CONNECT_DCM_MS - sync_elapsed
        if remaining > 0:
            utime.sleep_ms(remaining)
        self._send_info_sequence()
        self._wait_hub_ack()
        self._debug_connect = False
        if self.connected:
            self.last_nack = utime.ticks_ms()
            print("connect: ok id={} data=fast@115200".format(self.sensor_id))
            self.fast_uart()
        else:
            print("connect: failed id={} (slow@2400)".format(self.sensor_id))

    