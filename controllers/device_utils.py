import pigpio
from gpiozero import OutputDevice, InputDevice
from gpiozero.pins.pigpio import PiGPIOFactory
from threading import Thread, Event

from piir.io import receive
from piir.decode import decode
from piir.prettify import prettify


class DigitDisplayUtils:
    def __init__(self):
        pass


class LEDMultiCharDisplayWithShifter:
    LOW = 0
    HIGH = 1

    def __init__(self, digit_count, SDI, SRCLK, RCLK, display_pins):
        self.display_pins = display_pins
        self.RCLK = RCLK
        self.SRCLK = SRCLK
        self.SDI = SDI
        self.digit_count = digit_count
        self.digits = [0x0 for _ in range(digit_count)]
        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise IOError
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
