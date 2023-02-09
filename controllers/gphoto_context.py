from controllers.gphoto_context_base import GPhotoContextBase
import gphoto2 as gp
import time


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
        return self.camera.capture(gp.GP_CAPTURE_IMAGE)
