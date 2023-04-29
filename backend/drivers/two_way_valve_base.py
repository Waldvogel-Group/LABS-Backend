from backend.devices.base import *
from abc import ABC, abstractmethod

from twisted.internet import defer

from backend.commands.results import Result


class BaseDevice(AbstractBaseDevice, ABC):
    @abstractmethod
    def open(self, **kwargs): pass

    @abstractmethod
    def close(self, **kwargs): pass