"""
Module with wrapper for gphoto2 CLI util
"""
from gphoto_context_base import GPhotoContextBase
# pylint: disable=import-error
import gphoto2 as gp
import time
import subprocess
import os
import signal


class GPhotoContext(GPhotoContextBase):
    def __init__(self):
        self.camera = None
        self.maxRetry = 3

    def init_camera(self):
        self.camera = gp.Camera()
        print('Please connect and switch on your camera')
        i = 0
        while i < self.maxRetry:
            i += 1
            print("Init camera, try number: " + str(i))
            try:
                self.camera.init()
                print("camera init successfully!")
            except gp.GPhoto2Error as ex:
                print(ex)
                if ex.code == gp.GP_ERROR_MODEL_NOT_FOUND:
                    time.sleep(2)
                    continue
                raise
            break

    def capture_image(self):
        if self.camera is None:
            return None

        return self.camera.capture(gp.GP_CAPTURE_IMAGE)

    def unmount_camera(self):
        p = subprocess.Popen(["ps", "-A"], stdout=subprocess.PIPE)
        out, err = p.communicate()

        for line in out.splitlines():
            if b'-gphoto' in line:
                pid = int(line.split(None, 1)[0])
                os.kill(pid, signal.SIGKILL)
