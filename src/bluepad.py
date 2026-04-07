__author__ = "Anton Vanhoucke & Ste7an"
__copyright__ = "Copyright 2023, AntonsMindstorms.com"
__license__ = "GPL"
__version__ = "2.1.0"
__status__ = "Production"

# !! Upload this file into your editor at code.pybricks.com

from pybricks.iodevices import PUPDevice
import ustruct


FILL = 0x10
ZERO = 0x20
SET = 0x30
CONFIG = 0x40
WRITE = 0x80


class BluePad:
    """
    Class for using LMS-ESP32 running BluePad32 LPF2 firmware. Defines methods for reading
    connected Bluetooth gamepad (such as PS4 or Nintendo Switch) and for driving NeoPixels and Servo motors connected
    to the LMS-ESP32 board.
    Flash the LMS-ESP32 board with BluePad32 LPF2 for PyBricks projects from
    https://firmware.antonsmindstorms.com/.

    :param port: The port to which the LMS-ESp32 running BluePad32 is connected.
    :type port: Port (Example: Port.A)

    """

    def __init__(self, port):
        self.pup = PUPDevice(port)
        self.sensor_id = self.pup.info()["id"]
        self.cur_mode = 0
        self.nr_leds = 24
        self.arr_servos = [0] * 8

    def send(self, byte_vals):
        self.cur_mode = 0
        if self.sensor_id == 64:
            signed_vals = ustruct.unpack("9b", ustruct.pack("9B", *byte_vals))
            self.pup.write(self.cur_mode, signed_vals)
        else:
            word_vals = ustruct.unpack("8H", ustruct.pack("16B", *byte_vals))
            self.pup.write(self.cur_mode, word_vals)

    def gamepad(self, mode=-1, deadzone=5):
        """
        Returns the reading of a gamepad as a tuple. Returns the x- and y values of the left and right
        pads. Buttons are encoded as single bits in `buttonss`. The dpad values are encoded in `dpad`.

        :param deadzone: Axis values within [-deadzone, deadzone] are clamped to 0. Defaults to 5.
        :return: Tuple (left_pad_x,left_pad_y,right_pad_x,right_pad_y,buttons,dpad)
        """
        if mode >= 0:
            self.cur_mode = mode
        vals = self.pup.read(self.cur_mode)
        if self.sensor_id == 64:  # color matrix: 9 signed values
            if vals[0] == vals[1] == vals[2] == vals[3] == -128:
                return (0, 0, 0, 0, 0, 0)
            v0, v1, v2, v3 = vals[0], vals[1], vals[2], vals[3]
            btn, dpad = vals[4] & 255, vals[5] & 255
        else:  # color sensor id = 61: 8 unsigned words, axes in low bytes
            b = ustruct.pack("8H", *vals)
            if b[0] == b[1] == b[2] == b[3] == 0:  # axes all at -128 → no gamepad
                return (0, 0, 0, 0, 0, 0)
            v0, v1, v2, v3 = b[0]-128, b[1]-128, b[2]-128, b[3]-128
            btn, dpad = b[4], b[5]
        return (
            v0 if v0 > deadzone or v0 < -deadzone else 0,
            v1 if v1 > deadzone or v1 < -deadzone else 0,
            v2 if v2 > deadzone or v2 < -deadzone else 0,
            v3 if v3 > deadzone or v3 < -deadzone else 0,
            btn, dpad,
        )

    def btns_pressed(self, btns, nintendo=False):
        """
        Decodes the buttons pressed and converts the buttons to a string
        containing the pressed buttons ['X','O','[]','Δ']

        :param btns: The word read from the gamepad containing the binary encodeing of pressed buttons.
        :type btns: Word
        :param nintendo: Indicates that a nintendo gamepad is used.
        :return: String with pressed buttons.

        """
        bits_btns = [int(i) for i in bin(btns)[2:]]  # convert to binary, remove '0b'
        bits_btns.reverse()
        if nintendo:
            btn_val = ["B", "A", "Y", "X", "L", "R", "ZL", "ZR"]
        else:
            btn_val = ["X", "O", "[]", "V"]
        btns_string = [j for i, j in zip(bits_btns, btn_val) if i]
        return btns_string

    def dpad_pressed(self, btns, nintendo=False):
        """
        Decodes the dpad-buttons pressed and converts the buttons to a string
        containing the pressed buttons ['L','R','U','D']

        :param btns: The word read from the gamepad containing the binary encoding of pressed dpad-buttons
        :type btns: Word
        :return: String with pressed dpad-buttons

        """
        bits_btns = [int(i) for i in bin(btns)[2:]]  # convert to binary, remove '0b'
        bits_btns.reverse()
        if nintendo:
            btn_val = ["U", "D", "R", "L"]
        else:
            btn_val = ["D", "R", "L", "U"]
        btns_string = [j for i, j in zip(bits_btns, btn_val) if i]
        return btns_string

    def neopixel_init(self, nr_leds, pin):
        """
        Initializes a NeoPixel string with the given number of LEDs aconnected to the specified GPIO pin.

        :param nr_leds: The number of leds in the NeoPixel string
        :type nr_leds: byte
        :param pin: The GPIO pin number connected to the NeoPixel string
        :type pin: byte
        """
        leds = [0] * 16
        leds[0] = CONFIG
        leds[1] = nr_leds
        leds[2] = pin
        r = self.send(leds)
        self.cur_mode = 0
        self.nr_leds = nr_leds
        return r

    def neopixel_fill(self, color, write=True):
        """
        Fills all the neopixels with the same color.

        :param color: tuple with (r,g,b) colorsred color value
        :param write: If True write the output to the NeoPixels. Defaults to True.
        :type write: bool
        """
        global cur_mode
        r, g, b = color
        leds = [0] * 16
        leds[0] = FILL | WRITE if write else FILL
        leds[1:4] = [r, g, b]
        r = self.send(leds)
        self.cur_mode = 0
        return r

    def neopixel_zero(self, write=True):
        """
        Zeros all neopixels with value (0,0,0)

        :param write: If True writes the output to the NeoPixels. Defaults to False.
        :type write: bool
        """
        leds = [0] * 16
        leds[0] = ZERO | WRITE if write else FILL
        r = self.send(leds)
        self.cur_mode = 0
        return r

    def neopixel_set(self, led_nr, color, write=True):
        """
        Sets single NeoPixel at position led_nr with color=(r,g,b).

        :param led_nr: Position of the led to set (counting from 0)
        :type led_nr: byte
        :param color: Tuple with color for led (r,g,b)
        :param color: (r,g,b) with r,g,b bytes
        :param write: If True writes the output to the NeoPixels. Defaults to True.
        :type write: bool
        """
        r, g, b = color
        leds = [0] * 16
        leds[0] = SET | WRITE if write else FILL
        leds[1] = 1
        leds[2] = led_nr
        if led_nr >= self.nr_leds:
            print("error neopixel_set: led_nr larger than number of leds!")
            r = None
        else:
            leds[3:6] = [r, g, b]
            r = self.send(leds)
        self.cur_mode = 0
        return r

    def neopixel_set_multi(self, start_led, nr_led, led_arr, write=True):
        """
        Sets multiple NeoPixel value(s). Maximum number os leds is 4.

        :param start_led: Starting led number (counting from 0).
        :type start_led: byte
        :param nr_led: Number of leds to set.
        :type nr_led: byte
        :param led_arr: Array containing tuples r,g,b for each neopixel.
        :param write: If True write the output to the NeoPixels. Defaults to True.
        :type write: bool
        """
        leds = [0] * 16
        leds[0] = SET | WRITE if write else FILL
        leds[1] = nr_led
        leds[2] = start_led
        if nr_led > 4:
            print("error neopixel_set_multi: led_nr larger than 4!")
            r = None
        else:
            if len(led_arr) == 3 * nr_led:
                leds[3 : 3 + nr_led * 3] = led_arr
                r = self.send(leds)
            else:
                print(
                    "error neopixel_set_multi: led_nr does not correspons with led_arr"
                )
                r = None
        self.cur_mode = 0
        return r

    def servo(self, servo_nr, pos):
        """
        Sets Servo motor servo_nr to the specified position. Servo motors should be connected to
        GPIO pins 21, 22, 23 and 25 for LMS-ESP32v1 and to GPIO pins 19, 20, 21 and 22 for LMS-ESP32v2

        :param servo_nr: Servo motor counting from 0
        :type servo_nr: byte
        :param pos: Position of the Servo motor
        :type: word (2 byte int)
        """
        self.arr_servos[servo_nr] = pos % 181
        self.cur_mode = 1
        if self.sensor_id == 64:  # color matrix
            byte_vals = ustruct.unpack(
                "9b", ustruct.pack("4HB", *self.arr_servos[:4], 0)
            )
            r = self.pup.write(self.cur_mode, byte_vals)
        else:
            r = self.pup.write(self.cur_mode, self.arr_servos)
        return r

    def servos(self, servo_tgts, zero_is_mid=True):
        offset = 90 if zero_is_mid else 0
        self.arr_servos = [(tgt + offset) % 181 for tgt in servo_tgts[:4]]
        self.cur_mode = 1
        if self.sensor_id == 64:  # color matrix
            byte_vals = ustruct.unpack(
                "9b", ustruct.pack("4HB", *self.arr_servos[:4], 0)
            )
            r = self.pup.write(self.cur_mode, byte_vals)
        else:
            r = self.pup.write(self.cur_mode, self.arr_servos)
        return r


# Simple fucntions to import as blocks
from pybricks.parameters import Port, Color

rgb_values = {
    Color.WHITE: (255, 255, 255),
    Color.RED: (255, 0, 0),
    Color.ORANGE: (255, 127, 0),
    Color.BLACK: (0, 0, 0),
    Color.NONE: (0, 0, 0),
    Color.YELLOW: (255, 255, 0),
    Color.GREEN: (0, 255, 0),
    Color.CYAN: (0, 255, 255),
    Color.BLUE: (0, 0, 255),
    Color.VIOLET: (127, 127, 255),
    Color.MAGENTA: (255, 0, 255),
    Color.GRAY: (127, 127, 127),
}


def bluepad_init(port_letter, nintendo=True):
    global _bp
    global _nintendo
    port = eval("Port." + port_letter)
    _bp = BluePad(port)
    _nintendo = nintendo


def get_left_stick_vertical():
    # Return same direction and max value as Pybricks controller block
    return _bp.gamepad()[1] / 128 * -100


def get_left_stick_horizontal():
    # Return same direction and max value as Pybricks controller block
    return _bp.gamepad()[0] / 128 * 100


def get_right_stick_horizontal():
    # Return same direction and max value as Pybricks controller block
    return _bp.gamepad()[2] / 128 * 100


def get_right_stick_vertical():
    # Return same direction and max value as Pybricks controller block
    return _bp.gamepad()[3] / 128 * -100


def get_direction_pad():
    # Return same values as pybricks dpad block
    return _bp.gamepad()[5]


def get_buttons():
    # Return same values as pybricks dpad block
    return _bp.gamepad()[4]


def color_convert(color, intensity):
    c = (0, 0, 0)
    if color in rgb_values:
        color = rgb_values[color]
    if isinstance(color, tuple):
        c = tuple([int(val * intensity) for val in color])
    return c


def set_neopixel(led_nr, color, intensity=1, write=True):
    _bp.neopixel_set(led_nr, color_convert(color, intensity), write)


def init_neopixel(nr_leds, pin):
    _bp.neopixel_init(nr_leds, pin)


def fill_neopixel(color, intensity, write=True):
    _bp.neopixel_fill(color_convert(color, intensity), write)


def set_servo(servo_nr, angle):
    # Angle in range 0-180. 90 is neutral.
    _bp.servo(int(servo_nr), int(angle))


def gamepad():
    return _bp.gamepad()
