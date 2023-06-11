"""
Modules to interact with input and output devices connected to raspberry
"""

from threading import Thread, Event

import dataclasses
import pigpio
from gpiozero import InputDevice
from gpiozero.pins.pigpio import PiGPIOFactory

from piir.io import receive
from piir.decode import decode
from piir.prettify import prettify


class LEDAlphabet:
    """
    A Class represents alphabet convertor for 7-segment display
    Could be refactored with:
    https://github.com/gpiozero/gpiozero/blob/45bccc6201d393fec8f96271f94003fe20138c74/gpiozero/fonts.py
    """

    def __init__(self):
        self.data = self.load_alphabet()

    def get_char_code(self, char) -> int:
        """
        Save convert 7-segment codes to displayed character
        :param char:
        :return:
        """
        if char not in self.data:
            return 0x0
        return self.data[char]

    def load_alphabet(self):
        """
        Temporary mock function to return mapping from 7-segment pin codes to displayed letters
        :return:
        """
        return {
            '0': 0x3f,
            '1': 0x06,
            '2': 0x5b,
            '3': 0x4f,
            '4': 0x66,
            '5': 0x6d,
            '6': 0x7d,
            '7': 0x07,
            '8': 0x7f,
            '9': 0x6f,
            'E': 0x79,
            'r': 0x01,
            '-': 0x01,
            ')': 0x02,
            '(': 0x20,
            '_': 0x40,
            '@': 0x63
        }


@dataclasses.dataclass
class LEDMultiCharDisplayControlPins:
    """Data class for control pins"""
    sdi: int
    srclk: int
    rclk: int


class LEDMultiCharDisplayWithShifter:
    """A class represents output device to interact with 4-digit 7-segment display"""
    LOW = 0
    HIGH = 1

    # pylint: disable=unused-argument
    # @TODO: use lsb_first to customize bit numbering
    def __init__(self, digit_count, control_pins, display_pins, lsb_first=False):
        self.display_pins = display_pins
        self.control_pins = control_pins
        self.digit_count = digit_count
        self.value = [0x0 for _ in range(digit_count)]
        self.rpi = pigpio.pi()
        if not self.rpi.connected:
            raise IOError
        self._display_thread = Thread(target=self._display_value)
        self.alphabet = LEDAlphabet()
        self.setup()

    def setup(self):
        """Put low power on all used pins"""
        self.rpi.set_mode(self.control_pins.sdi, pigpio.OUTPUT)
        self.rpi.write(self.control_pins.sdi, self.LOW)
        self.rpi.set_mode(self.control_pins.rclk, pigpio.OUTPUT)
        self.rpi.write(self.control_pins.rclk, self.LOW)
        self.rpi.set_mode(self.control_pins.srclk, pigpio.OUTPUT)
        self.rpi.write(self.control_pins.srclk, self.LOW)

        for i in self.display_pins:
            self.rpi.write(i, pigpio.OUTPUT)

    def clear_display(self):
        """Clear single 7-segment display element"""
        for _ in range(8):
            self.rpi.write(self.control_pins.sdi, self.LOW)
            self.rpi.write(self.control_pins.srclk, self.HIGH)
            self.rpi.write(self.control_pins.srclk, self.LOW)
        self.rpi.write(self.control_pins.rclk, self.HIGH)
        self.rpi.write(self.control_pins.rclk, self.LOW)

    def hc595_shift(self, data):
        """
        Shift data to 74HC595 block
        :param data: binary code
        :return:
        """
        for i in range(8):
            self.rpi.write(self.control_pins.sdi, 0x80 & (data << i) == 0x80)
            self.rpi.write(self.control_pins.srclk, self.HIGH)
            self.rpi.write(self.control_pins.srclk, self.LOW)
        self.rpi.write(self.control_pins.rclk, self.HIGH)
        self.rpi.write(self.control_pins.rclk, self.LOW)

    def pick_digit(self, digit):
        """
        Set active 7-segment element number to interact with
        :param digit: element number from beginning
        :return:
        """
        for i in self.display_pins:
            self.rpi.write(i, self.HIGH)
        self.rpi.write(self.display_pins[digit], self.LOW)

    def set_value_code(self, code, index, decimal_point=False):
        """
        Put binary display code
        :param code:
        :param index:
        :param decimal_point:
        :return:
        """
        code = code | 128 if decimal_point else code
        self.value[index] = code

    def set_value_char(self, char, index, decimal_point=False):
        """
        Set letter to display
        :param char:
        :param index:
        :param decimal_point:
        :return:
        """
        char_code = self.alphabet.get_char_code(char)
        self.value[index] = char_code | 128 if decimal_point else char_code

    def start(self):
        """Start display updating thread"""
        self._display_thread.start()

    def display_value(self):
        """Display selected info on LED display from self.value"""
        for i, hex_val in enumerate(self.value):
            self.clear_display()
            self.pick_digit(i)
            self.hc595_shift(hex_val)

    def _display_value(self):
        while True:
            self.display_value()


class IRReceiver(InputDevice):
    """
    A class to represent interaction with infrared receiver device
    """
    def __init__(self, pin, callback):
        self.factory = PiGPIOFactory()
        super().__init__(pin, pin_factory=self.factory)
        self._read_thread = Thread(target=self._read_ir, args=(pin, callback))
        self._stop_event = Event()
        self._stop_event.clear()

    def start(self):
        """Start receiving process"""
        self._read_thread.start()

    def stop(self):
        """Stop receiving process"""
        self._stop_event.set()

    def _read_ir(self, pin, callback):
        keys = {}
        while not self._stop_event.is_set():
            data = decode(receive(pin))
            if data:
                keys['last'] = data
                data_parsed = prettify(keys)
                print(data_parsed)
                pressed_keys = data_parsed['keys']['last']
                if isinstance(pressed_keys, str):
                    last = [pressed_keys]
                elif isinstance(pressed_keys, list):
                    last = pressed_keys
                else:
                    print('unknown pressed key type')
                    continue

                callback(last)
