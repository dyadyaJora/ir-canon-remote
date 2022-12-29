import RPi.GPIO as GPIO
import multiprocessing
import math
import subprocess
import os
import signal
import gphoto2 as gp
import time

from piir.io import receive
from piir.decode import decode
from piir.prettify import prettify

time_laps_thread = None
camera = None
# @TODO: from string to singleton objects
DISPLAY_MODES = ["DELAY", "COUNTER", "TIMER"]
MODE = multiprocessing.Value('i', 0)

STATES = ["WAITING", "RUNNING", "ERROR"]
STATE = multiprocessing.Value('i', 0)

MAX_DELAY = 100
# @TODO move to class fields
delay = multiprocessing.Value('i', 1)
time_left = multiprocessing.Value('i', 2)
count = multiprocessing.Value('i', 0)

MAX_RETRY = 3
SDI = 24
RCLK = 23
SRCLK = 18
IRINPUT = 25

displayPin = (10, 22, 27, 17)
number = (0x3f, 0x06, 0x5b, 0x4f, 0x66, 0x6d, 0x7d, 0x07, 0x7f, 0x6f)

ir_codes = {
    "DOWN": 7,
    "UP": 15,
    "PREV": 44,
    "NEXT": 40,
    "PLAY": 43,
    "EQ": 9
}


def clear_display():
    for i in range(8):
        GPIO.output(SDI, 0)
        GPIO.output(SRCLK, GPIO.HIGH)
        GPIO.output(SRCLK, GPIO.LOW)
    GPIO.output(RCLK, GPIO.HIGH)
    GPIO.output(RCLK, GPIO.LOW)


def hc595_shift(data):
    for i in range(8):
        GPIO.output(SDI, 0x80 & (data << i))
        GPIO.output(SRCLK, GPIO.HIGH)
        GPIO.output(SRCLK, GPIO.LOW)
    GPIO.output(RCLK, GPIO.HIGH)
    GPIO.output(RCLK, GPIO.LOW)


def pick_digit(digit):
    for i in displayPin:
        GPIO.output(i, GPIO.HIGH)
    GPIO.output(displayPin[digit], GPIO.LOW)


def setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(SDI, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(RCLK, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(SRCLK, GPIO.OUT, initial=GPIO.LOW)

    for i in displayPin:
        GPIO.setup(i, GPIO.OUT)

    action_reset()

    ir_receive_thread = multiprocessing.Process(target=read_ir, args=(delay, MODE, STATE))
    ir_receive_thread.start()


def loop():
    # https://github.com/gpiozero/gpiozero/blob/45bccc6201d393fec8f96271f94003fe20138c74/gpiozero/fonts.py
    while True:
        print_display()
        print_status()
        #time.sleep(1)
        #print(delay)


def print_status():
    print_digit(STATE.value, 3, dp=True)


def print_display():
    if DISPLAY_MODES[MODE.value] == "DELAY":
        print_3digit(delay.value)
    elif DISPLAY_MODES[MODE.value] == "COUNTER":
        print_3digit(count.value)
    else:
        print_3digit(time_left.value)


def print_3digit(n):
    print_digit(n % 10, 0)
    print_digit(n % 100 // 10, 1)
    print_digit(n % 1000 // 100, 2)


def print_digit(n, i, dp=False):
    clear_display()
    pick_digit(i)
    hex_val = number[n] | 128 if dp else number[n]
    # hex_val = number[n]
    hc595_shift(hex_val)


def destroy():
    GPIO.cleanup()


def read_ir(d, mode, state):
    keys = {}

    while True:
        data = decode(receive(IRINPUT))
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
                if ir_codes['EQ'] == ir_code:
                    action_reset()
                elif STATES[STATE.value] == 'ERROR':
                    break
                else:
                    if ir_codes['PREV'] == ir_code:
                        action_next_display(mode)
                    elif ir_codes['NEXT'] == ir_code:
                        action_next_display(mode, is_forward=False)
                    else:
                        if STATES[STATE.value] == 'WAITING':
                            if ir_codes['UP'] == ir_code:
                                action_inc_delay(d)
                            elif ir_codes['DOWN'] == ir_code:
                                action_dec_delay(d)
                            elif ir_codes['PLAY'] == ir_code:
                                action_play(state)
                            else:
                                print("unknown command")
                        elif STATES[STATE.value] == 'RUNNING':
                            if ir_codes['PLAY'] == ir_code:
                                action_pause(state)
                            else:
                                print("unknown command")
                        else:
                            print("unknown command")


def action_inc_delay(d):
    d.value = (d.value + 1) % MAX_DELAY
    print("NEW_DELAY" + str(d))


def action_dec_delay(d):
    d.value = (d.value - 1) % MAX_DELAY
    print("NEW_DELAY" + str(d))


def action_next_display(mode, is_forward=True):
    i = mode.value
    if is_forward:
        i += 1
    else:
        i -= 1
    mode.value = i % len(DISPLAY_MODES)


def action_play(state):
    global time_laps_thread
    print("BEFORE" + str(time_laps_thread))
    time_laps_thread = multiprocessing.Process(target=start_time_laps, args=(delay, count))
    time_laps_thread.start()
    # @TODO: change status only if thread started
    state.value = STATES.index('RUNNING')
    print("AFTER" + str(time_laps_thread))


def action_pause(state):
    print(time_laps_thread)
    if time_laps_thread is not None:
        time_laps_thread.terminate()
        state.value = STATES.index('WAITING')


def action_reset():
    print("Resetting...")
    delay.value = 1
    time_left.value = 2
    count.value = 0
    unmount_camera()
    init_camera()
    print("Reset was complete!")


def unmount_camera():
    p = subprocess.Popen(["ps", "-A"], stdout=subprocess.PIPE)
    out, err = p.communicate()

    for line in out.splitlines():
        if b'-gphoto' in line:
            pid = int(line.split(None, 1)[0])
            os.kill(pid, signal.SIGKILL)


def init_camera():
    global camera
    camera = gp.Camera()
    print('Please connect and switch on your camera')
    i = 0
    while i < MAX_RETRY:
        i += 1
        print("Init camera, try number: " + str(i))
        try:
            camera.init()
            print("camera init successfully!")
        except gp.GPhoto2Error as ex:
            print(ex)
            if ex.code == gp.GP_ERROR_MODEL_NOT_FOUND:
                time.sleep(2)
                continue
            raise
        break


def start_time_laps(d, c):
    while True:
        print('Capturing image')
        file_path = camera.capture(gp.GP_CAPTURE_IMAGE)
        c.value += 1
        print('Camera file path: {0}/{1}'.format(file_path.folder, file_path.name))
        print('Count: ' + str(c))
        time.sleep(d.value)


if __name__ == '__main__':
    setup()
    try:
        loop()
    except KeyboardInterrupt:
        destroy()


class ApplicationContext:
    def __init__(self):
        pass


class IRActionDispatcher:
    def __init__(self):
        pass


class GPhotoContext:
    def __init__(self):
        self.camera = None


class DigitDisplayUtils:
    def __init__(self):
        pass
