import pigpio
import threading
import time
import enum

from controllers.device_utils import IRReceiver, LEDMultiCharDisplayWithShifter

try:
    from controllers.gphoto_context import GPhotoContext
except ImportError:
    from controllers.gphoto_context_mock import GPhotoContextMock as GPhotoContext

from controllers.ir_codes_data import IRCodesData


class State(enum.Enum):
    WAITING = 0
    RUNNING = 1
    ERROR = 2


class DisplayMode(enum.Enum):
    DELAY = 0
    COUNTER = 1
    TIMER = 2


class ApplicationContext:
    time_laps_thread = None
    camera = None
    ir_codes = None
    gpContext = GPhotoContext()

    MAX_DELAY = 100

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
        self.ir_receiver = None
        self.led_display = None

        self.time_laps_thread = None
        self._stop_event = threading.Event()
        self._stop_event.is_set()

        self._status = State.WAITING
        self._mode = DisplayMode.DELAY

        self._delay = 1
        self._time_left = 2
        self._count = 0

    @property
    def delay(self):
        return self._delay

    @delay.setter
    def delay(self, value):
        self._delay = value

        if DisplayMode.DELAY == self._mode:
            self.print_3digit_to_led(self._delay)

    @property
    def count(self):
        return self._count

    @count.setter
    def count(self, value):
        self._count = value

        if DisplayMode.COUNTER == self._mode:
            self.print_3digit_to_led(self._count)

    @property
    def time_left(self):
        return self._time_left

    @time_left.setter
    def time_left(self, value):
        self._time_left = value

        if DisplayMode.TIMER == self._mode:
            self.print_3digit_to_led(self._time_left)

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        self._status = value

        self.led_display.set_value_char(str(self._status.value), 3, dp=True)

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, value):
        self._mode = value

        if DisplayMode.DELAY == self._mode:
            self.print_3digit_to_led(self._delay)
        elif DisplayMode.COUNTER == self._mode:
            self.print_3digit_to_led(self._count)
        else:
            self.print_3digit_to_led(self._time_left)

    def print_3digit_to_led(self, n):
        self.led_display.set_value_char(str(n % 10), 0)
        self.led_display.set_value_char(str(n % 100 // 10), 1)
        self.led_display.set_value_char(str(n % 1000 // 100), 2)

    def setup(self):
        ir_loader = IRCodesData()
        self.ir_codes = ir_loader.load()

        self.led_display = LEDMultiCharDisplayWithShifter(4, self.SDI, self.SRCLK, self.RCLK, self.displayPin)
        self.action_reset()

        # self.led_display.start()

        self.ir_receiver = IRReceiver(self.IRINPUT, self.handle_ir_code)
        self.ir_receiver.start()

    def loop(self):
        while True:
            self.led_display.display_value()

    def destroy(self):
        self.pi.stop()

    def handle_ir_code(self, last):
        for l in last:
            try:
                ir_code = int(l.replace(' ', ''))
            except ValueError:
                print('could not parse int code from: ' + l)
                continue

            if self.ir_codes['EQ'] == ir_code:
                self.action_reset()
            elif State.ERROR == self.status:
                break
            else:
                if self.ir_codes['PREV'] == ir_code:
                    self.action_next_display()
                elif self.ir_codes['NEXT'] == ir_code:
                    self.action_next_display(is_forward=False)
                else:
                    if State.WAITING == self.status:
                        if self.ir_codes['UP'] == ir_code:
                            self.action_inc_delay()
                        elif self.ir_codes['DOWN'] == ir_code:
                            self.action_dec_delay()
                        elif self.ir_codes['PLAY'] == ir_code:
                            self.action_play()
                        else:
                            print("unknown command")
                    elif State.RUNNING == self.status:
                        if self.ir_codes['PLAY'] == ir_code:
                            self.action_pause()
                        else:
                            print("unknown command")
                    else:
                        print("unknown command")

    def action_inc_delay(self):
        self.delay = (self.delay + 1) % self.MAX_DELAY
        print("NEW_DELAY" + str(self.delay))

    def action_dec_delay(self):
        self.delay = (self.delay - 1) % self.MAX_DELAY
        print("NEW_DELAY" + str(self.delay))

    def action_next_display(self, is_forward=True):
        i = self.mode.value
        if is_forward:
            i += 1
        else:
            i -= 1
        i = i % len(DisplayMode)
        self.mode = DisplayMode(i)

    def action_play(self):
        print("BEFORE" + str(self.time_laps_thread))
        self._stop_event.clear()
        self.time_laps_thread = threading.Thread(target=self.start_time_laps)
        self.time_laps_thread.start()
        # @TODO: change status only if thread started
        self.status = State.RUNNING
        print("AFTER" + str(self.time_laps_thread))

    def action_pause(self):
        print(self.time_laps_thread)
        if self.time_laps_thread is not None:
            self._stop_event.set()
            # self.time_laps_thread = None
            self.status = State.WAITING

    def action_reset(self):
        print("Resetting...")
        self.delay = 1
        self.time_left = 2
        self.count = 0
        self.action_pause()
        self.status = State.WAITING
        self.gpContext.unmount_camera()
        self.gpContext.init_camera()
        print("Reset was complete!")

    def start_time_laps(self):
        while not self._stop_event.is_set():
            print('Capturing image')
            file_path = self.gpContext.capture_image()
            self.count = self.count + 1
            if file_path is not None:
                print('Camera file path: {0}/{1}'.format(file_path.folder, file_path.name))
            print('Count: ' + str(self.count))
            time.sleep(self.delay)

    def run(self):
        self.setup()
        try:
            self.loop()
        except KeyboardInterrupt:
            self.destroy()


if __name__ == '__main__':
    ApplicationContext().run()
