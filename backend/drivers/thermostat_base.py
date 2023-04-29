from backend.devices.base import *
from abc import ABC, abstractmethod


class BaseDevice(ABC):

    @abstractmethod
    def set_temperature(self, temperature, **kwargs): pass

    @abstractmethod
    def get_current_temperature(self, **kwargs): pass

    @abstractmethod
    def stop_tempering(self, **kwargs): pass
    