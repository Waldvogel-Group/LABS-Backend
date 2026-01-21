from backend.devices.base import *
from abc import ABC, abstractmethod


class BaseDevice(ABC):

    @abstractmethod
    def start_measurement(self, **kwargs): pass

    @abstractmethod
    def start_shimming(self, **kwargs): pass

    @abstractmethod
    def stop_measurement(self, **kwargs): pass

    #TODO: more methods needed?