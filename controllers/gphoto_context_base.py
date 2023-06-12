"""
Module with abstract class for gphoto2 wrapper
"""
import abc


class GPhotoContextBase(abc.ABC):
    """
    Wrapper class for g2hoto2 util
    """
    @abc.abstractmethod
    def init_camera(self):
        """
        function to initialize camera as input device
        :return:
        """

    @abc.abstractmethod
    def capture_image(self):
        """
        function to take a photo
        :return:
        """

    @abc.abstractmethod
    def unmount_camera(self):
        """
        release camera input device resources
        :return:
        """
