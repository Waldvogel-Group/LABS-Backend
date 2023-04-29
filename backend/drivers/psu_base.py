from backend.devices.base import *
from abc import ABC, abstractmethod


class BaseDevice(AbstractBaseDevice, ABC):

    @abstractmethod
    def output_constant_current(self, current, max_voltage, amount_of_charge=None): pass

    @abstractmethod
    def output_constant_voltage(self, voltage, max_current, amount_of_charge=None): pass

    @abstractmethod
    def stop_current(self, *args, **kwargs): pass
