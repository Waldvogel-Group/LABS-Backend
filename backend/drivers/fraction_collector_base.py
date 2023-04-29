from backend.devices.base import *
from abc import ABC, abstractmethod


class BaseDevice(ABC):

    @abstractmethod
    def next_fraction(self): pass

    @abstractmethod
    def previous_fraction(self): pass

    @abstractmethod
    def reset_to_start(self): pass
