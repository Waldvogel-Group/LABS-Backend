from backend.devices.base import *
from abc import ABC, abstractmethod


class BaseDevice(ABC):

    @abstractmethod
    def dispense(self, rate, volume, **kwargs): pass

    @abstractmethod
    def continuous_flow(self, rate, **kwargs): pass

    @abstractmethod
    def stop_pumping(self, **kwargs): pass
