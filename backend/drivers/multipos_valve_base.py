from backend.devices.base import *
from abc import ABC, abstractmethod

from twisted.internet import defer

from backend.commands.results import Result


class BaseDevice(AbstractBaseDevice, ABC):

    def __init__(self, address, *args, **kwargs):
        super().__init__(address, *args, **kwargs)
        self.positions = None

    def initial_commands(self):
        self._get_valve_positions().deferred_result.addCallback(self._set_valve_positions)
        super().initial_commands()

    @abstractmethod
    def _get_valve_positions(self) -> defer.Deferred: pass

    def _set_valve_positions(self, result: Result) -> Result:
        self.positions = int(result.parameters["position_count"])  # position_count must be in RE Parser
        return result

    @abstractmethod
    def set_position(self, position, **kwargs): pass

    @abstractmethod
    def next_position(self, **kwargs): pass

    @abstractmethod
    def previous_position(self, **kwargs): pass
