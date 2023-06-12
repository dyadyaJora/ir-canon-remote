"""
Module with mock of gphoto2 util
"""
import time
from gphoto_context_base import GPhotoContextBase


class GPhotoContextMock(GPhotoContextBase):
    """
    Class represents a mock for gphoto2 util
    """
    def __init__(self):
        pass

    def init_camera(self):
        """
        Mock of camera initialization
        """
        print("Initializing camera...")
        time.sleep(2)
        print("Initialization complete!")

    def capture_image(self):
        """
        Mock of image capture
        :return:
        """
        print("Capturing image...")
        time.sleep(2)
        print("Capture complete!")

    def unmount_camera(self):
        """
        Mock of camera unmount
        :return:
        """
        print("Unmount camera mock")
