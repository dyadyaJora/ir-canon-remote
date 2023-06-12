"""
Module for IR remote codes mapping
"""


# pylint: disable=too-few-public-methods
# @TODO: move "load" to enum and delete this module
class IRCodesData:
    """
    A class represents IR codes mapping
    """
    def __init__(self):
        pass

    def load(self):
        """
        Function for loading mapping of IR remote buttons to signal codes
        :return:
        """
        return {
            "DOWN": 7,
            "UP": 15,
            "PREV": 44,
            "NEXT": 40,
            "PLAY": 43,
            "EQ": 9
        }
