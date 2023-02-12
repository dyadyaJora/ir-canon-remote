from controllers.gphoto_context_base import GPhotoContextBase
import time


class GPhotoContextMock(GPhotoContextBase):
    def __init__(self):
        pass

    def init_camera(self):
        print("Initializing camera...")
        time.sleep(2)
        print("Initialization complete!")

    def capture_image(self):
        print("Capturing image...")
        time.sleep(2)
        print("Capture complete!")

    def unmount_camera(self):
        print("Unmount camera mock")
