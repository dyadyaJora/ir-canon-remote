"""
Modules to interact with input and output devices connected to raspberry
"""

import pigpio
from gpiozero import OutputDevice, InputDevice
from gpiozero.pins.pigpio import PiGPIOFactory
from threading import Thread, Event

from piir.io import receive
from piir.decode import decode
from piir.prettify import prettify


class LEDAlphabet:
    # https://github.com/gpiozero/gpiozero/blob/45bccc6201d393fec8f96271f94003fe20138c74/gpiozero/fonts.py
    def __init__(self):
        self.data = self.load()

    def get_char_code(self, char) -> int:
        if char not in self.data:
            return 0x0
        return self.data[char]

    def load(self):
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


class LEDMultiCharDisplayWithShifter:
    LOW = 0
    HIGH = 1

    def __init__(self, digit_count, SDI, SRCLK, RCLK, display_pins, lsb_first=False):
        self.display_pins = display_pins
        self.RCLK = RCLK
        self.SRCLK = SRCLK
        self.SDI = SDI
        self.digit_count = digit_count
        self.value = [0x0 for _ in range(digit_count)]
        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise IOError
        self._display_thread = Thread(target=self._display_value)
        self.alphabet = LEDAlphabet()
        self.setup()

    def setup(self):
        self.pi.set_mode(self.SDI, pigpio.OUTPUT)
        self.pi.write(self.SDI, self.LOW)
        self.pi.set_mode(self.RCLK, pigpio.OUTPUT)
        self.pi.write(self.RCLK, self.LOW)
        self.pi.set_mode(self.SRCLK, pigpio.OUTPUT)
        self.pi.write(self.SRCLK, self.LOW)

        for i in self.display_pins:
            self.pi.write(i, pigpio.OUTPUT)

    def clear_display(self):
        for i in range(8):
            self.pi.write(self.SDI, self.LOW)
            self.pi.write(self.SRCLK, self.HIGH)
            self.pi.write(self.SRCLK, self.LOW)
        self.pi.write(self.RCLK, self.HIGH)
        self.pi.write(self.RCLK, self.LOW)

    def hc595_shift(self, data):
        for i in range(8):
            self.pi.write(self.SDI, 0x80 & (data << i) == 0x80)
            self.pi.write(self.SRCLK, self.HIGH)
            self.pi.write(self.SRCLK, self.LOW)
        self.pi.write(self.RCLK, self.HIGH)
        self.pi.write(self.RCLK, self.LOW)

    def pick_digit(self, digit):
        for i in self.display_pins:
            self.pi.write(i, self.HIGH)
        self.pi.write(self.display_pins[digit], self.LOW)

    def set_value_code(self, code, index, dp=False):
        code = code | 128 if dp else code
        self.value[index] = code

    def set_value_char(self, char, index, dp=False):
        char_code = self.alphabet.get_char_code(char)
        self.value[index] = char_code | 128 if dp else char_code

    def start(self):
        self._display_thread.start()

    def display_value(self):
        for i in range(len(self.value)):
            self.clear_display()
            hex_val = self.value[i]
            self.pick_digit(i)
            self.hc595_shift(hex_val)

    def _display_value(self):
        while True:
            self.display_value()


class IRReceiver(InputDevice):
    def __init__(self, pin, callback):
        self.factory = PiGPIOFactory()
        super(IRReceiver, self).__init__(pin, pin_factory=self.factory)
        self._read_thread = Thread(target=self._read_ir, args=(pin, callback))
        self._stop_event = Event()
        self._stop_event.clear()

    def start(self):
        self._read_thread.start()

    def stop(self):
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
                if type(pressed_keys) is str:
                    last = [pressed_keys]
                elif type(pressed_keys) is list:
                    last = pressed_keys
                else:
                    print('unknown pressed key type')
                    continue

                callback(last)
