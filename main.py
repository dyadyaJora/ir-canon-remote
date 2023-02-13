import pigpio
# import multiprocessing
import threading
import time

try:
    from controllers.gphoto_context import GPhotoContext
except ImportError:
    from controllers.gphoto_context_mock import GPhotoContextMock as GPhotoContext

from piir.io import receive
from piir.decode import decode
from piir.prettify import prettify
from controllers.ir_codes_data import IRCodesData


class ApplicationContext:
    time_laps_thread = None
    camera = None
    ir_codes = None
    gpContext = GPhotoContext()
    # @TODO: from string to singleton objects
    DISPLAY_MODES = ["DELAY", "COUNTER", "TIMER"]
    # MODE = multiprocessing.Value('i', 0)
    MODE = 0

    STATES = ["WAITING", "RUNNING", "ERROR"]
    # STATE = multiprocessing.Value('i', 0)
    STATE = 0

    MAX_DELAY = 100
    # @TODO move to class fields
    # delay = multiprocessing.Value('i', 1)
    delay = 1
    # time_left = multiprocessing.Value('i', 2)
    time_left = 2
    # count = multiprocessing.Value('i', 0)
    count = 0

    SDI = 24
    RCLK = 23
    SRCLK = 18
    IRINPUT = 25

    LOW = 0
    HIGH = 1

    displayPin = (10, 22, 27, 17)
    number = (0x3f, 0x06, 0x5b, 0x4f, 0x66, 0x6d, 0x7d, 0x07, 0x7f, 0x6f)

    def __init__(self):
        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise IOError

    def clear_display(self):
        for i in range(8):
            self.pi.write(self.SDI, self.LOW)
            self.pi.write(self.SRCLK, self.HIGH)
            self.pi.write(self.SRCLK, self.LOW)
        self.pi.write(self.RCLK, self.HIGH)
        self.pi.write(self.RCLK, self.LOW)

    def hc595_shift(self, data):
        for i in range(8):
            self.pi.write(self.SDI, 0x80 & (data << i))
            self.pi.write(self.SRCLK, self.HIGH)
            self.pi.write(self.SRCLK, self.LOW)
        self.pi.write(self.RCLK, self.HIGH)
        self.pi.write(self.RCLK, self.LOW)

    def pick_digit(self, digit):
        for i in self.displayPin:
            self.pi.write(i, self.HIGH)
        self.pi.write(self.displayPin[digit], self.LOW)

    def setup(self):
        ir_loader = IRCodesData()
        self.ir_codes = ir_loader.load()

        self.pi.set_mode(self.SDI, pigpio.OUTPUT)
        self.pi.write(self.SDI, self.LOW)
        self.pi.set_mode(self.RCLK, pigpio.OUTPUT)
        self.pi.write(self.RCLK, self.LOW)
        self.pi.set_mode(self.SRCLK, pigpio.OUTPUT)
        self.pi.write(self.SRCLK, self.LOW)

        for i in self.displayPin:
            self.pi.write(i, pigpio.OUTPUT)

        self.action_reset()

        ir_receive_thread = threading.Thread(target=self.read_ir, args=(self.delay, self.MODE, self.STATE))
        ir_receive_thread.start()

    def loop(self):
        # https://github.com/gpiozero/gpiozero/blob/45bccc6201d393fec8f96271f94003fe20138c74/gpiozero/fonts.py
        while True:
            self.print_display()
            self.print_status()
            # time.sleep(1)
            # print(delay)

    def print_status(self):
        self.print_digit(self.STATE, 3, dp=True)

    def print_display(self):
        if self.DISPLAY_MODES[self.MODE] == "DELAY":
            self.print_3digit(self.delay)
        elif self.DISPLAY_MODES[self.MODE] == "COUNTER":
            self.print_3digit(self.count)
        else:
            self.print_3digit(self.time_left)

    def print_3digit(self, n):
        self.print_digit(n % 10, 0)
        self.print_digit(n % 100 // 10, 1)
        self.print_digit(n % 1000 // 100, 2)

    def print_digit(self, n, i, dp=False):
        self.clear_display()
        self.pick_digit(i)
        hex_val = self.number[n] | 128 if dp else self.number[n]
        # hex_val = number[n]
        self.hc595_shift(hex_val)

    def destroy(self):
        self.pi.stop()

    def read_ir(self, d, mode, state):
        keys = {}

        while True:
            data = decode(receive(self.IRINPUT))
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

                for l in last:
                    ir_code = int(l.replace(' ', ''))
                    if self.ir_codes['EQ'] == ir_code:
                        self.action_reset()
                    elif self.STATES[self.STATE.value] == 'ERROR':
                        break
                    else:
                        if self.ir_codes['PREV'] == ir_code:
                            self.action_next_display(mode)
                        elif self.ir_codes['NEXT'] == ir_code:
                            self.action_next_display(mode, is_forward=False)
                        else:
                            if self.STATES[self.STATE.value] == 'WAITING':
                                if self.ir_codes['UP'] == ir_code:
                                    self.action_inc_delay(d)
                                elif self.ir_codes['DOWN'] == ir_code:
                                    self.action_dec_delay(d)
                                elif self.ir_codes['PLAY'] == ir_code:
                                    self.action_play(state)
                                else:
                                    print("unknown command")
                            elif self.STATES[self.STATE.value] == 'RUNNING':
                                if self.ir_codes['PLAY'] == ir_code:
                                    self.action_pause(state)
                                else:
                                    print("unknown command")
                            else:
                                print("unknown command")

    def action_inc_delay(self, d):
        d.value = (d.value + 1) % self.MAX_DELAY
        print("NEW_DELAY" + str(d))

    def action_dec_delay(self, d):
        d.value = (d.value - 1) % self.MAX_DELAY
        print("NEW_DELAY" + str(d))

    def action_next_display(self, mode, is_forward=True):
        i = mode.value
        if is_forward:
            i += 1
        else:
            i -= 1
        mode.value = i % len(self.DISPLAY_MODES)

    def action_play(self, state):
        print("BEFORE" + str(self.time_laps_thread))
        time_laps_thread = threading.Thread(target=self.start_time_laps, args=(self.delay, self.count))
        time_laps_thread.start()
        # @TODO: change status only if thread started
        state.value = self.STATES.index('RUNNING')
        print("AFTER" + str(time_laps_thread))

    def action_pause(self, state):
        print(self.time_laps_thread)
        if self.time_laps_thread is not None:
            self.time_laps_thread.terminate()
            state.value = self.STATES.index('WAITING')

    def action_reset(self):
        print("Resetting...")
        self.delay = 1
        self.time_left = 2
        self.count = 0
        self.gpContext.unmount_camera()
        self.gpContext.init_camera()
        print("Reset was complete!")

    def start_time_laps(self, d, c):
        while True:
            print('Capturing image')
            file_path = self.gpContext.capture_image()
            c.value += 1
            if file_path is not None:
                print('Camera file path: {0}/{1}'.format(file_path.folder, file_path.name))
            print('Count: ' + str(c))
            time.sleep(d.value)

    def run(self):
        self.setup()
        try:
            self.loop()
        except KeyboardInterrupt:
            self.destroy()


if __name__ == '__main__':
    ApplicationContext().run()


