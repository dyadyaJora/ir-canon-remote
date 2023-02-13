import abc


class GPhotoContextBase(abc.ABC):
    @abc.abstractmethod
    def init_camera(self):
        pass

    @abc.abstractmethod
    def capture_image(self):
        pass

    @abc.abstractmethod
    def unmount_camera(self):
        pass
