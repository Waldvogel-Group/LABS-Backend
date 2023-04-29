from __future__ import annotations
from multiprocessing.connection import wait
from typing import TYPE_CHECKING

from twisted.internet import reactor, defer, task

from abc import ABC
from .helpers_exceptions import DeviceShutdownError, DeviceErrorError
from backend.helpers_exceptions import IState


if TYPE_CHECKING:
    from backend.commands import ABDeviceCommand


class DeviceState(IState, ABC):
    def __init__(self, device, *args, **kwargs):
        self.device = device

    def send_cmd(self, cmd: ABDeviceCommand):
        if cmd.parameters.urgent:
            pos = 0
            for queued_cmd in self.device.cmd_queue:
                if queued_cmd.parameters.urgent:
                    pos += 1
                else:
                    break
            self.device.cmd_queue.insert(pos, cmd)
        else:
            self.device.cmd_queue.append(cmd)

    def handle_success(self, result):
        cmd = result.command
        return task.deferLater(reactor, cmd.parameters.inter_command_time, self.device.set_state, result,
                                cmd.parameters.next_devicestate).addCallback(lambda _: result)

    def handle_fail(self, failure):
        cmd = failure.value.command
        cmd.device.state = Error
        return failure

    def add_command_callbacks(self, cmd):
        def success(result):
            return self.device.stateobject.handle_success(result)
        def fail(result):
            return self.device.stateobject.handle_fail(result)
        cmd.deferred_result.addCallbacks(success, fail)

    def new_state(self, state, *args, **kwargs):
        """
        Setting states is delegated to the current state, so that in Shutdown- or Errorstate it can be ignored.
        :param *args:
        :param **kwargs:
        :param state:
        :return:
        """
        self.device.stateobject = state


class NotReady(DeviceState):
    def enter(self):
        pass


class CollectingCommands(DeviceState):
    def __init__(self, device):
        super().__init__(device)
        self.commandseries = None  # set by CommandSeries

    def enter(self):
        pass

    def send_cmd(self, cmd: ABDeviceCommand):
        if cmd.parameters.urgent:
            self.commandseries.parameters.urgent = True
        self.commandseries.commandlist.append(cmd)

    def add_command_callbacks(self, cmd):
        pass


class Ready(DeviceState):
    def enter(self):
        try:
            cmd = self.device.cmd_queue.pop(0)
        except IndexError:
            pass
        else:
            self.send_cmd(cmd)

    def send_cmd(self, cmd: ABDeviceCommand):
        self.device.execute_cmd(cmd)
        self.device.state = cmd.parameters.devicestate_while_executing


class Initializing(Ready):
    def enter(self): pass


class Error(DeviceState):
    def enter(self):
        self.device.cmd_queue = []

    def send_cmd(self, cmd: ABDeviceCommand):
        error = DeviceErrorError("Cannot send commands in Error state!")
        self.device.log.error(f"{str(error)}")
        raise error

    def new_state(self, state, *args, **kwargs):
        pass


class Stopped(DeviceState):
    def enter(self):
        self.device.cmd_queue = []

    def send_cmd(self, cmd: ABDeviceCommand):
        self.device.log.error("Device stopped, cannot send Commands in this state.")


class Shutdown(DeviceState):
    def enter(self):
        try:
            self.device.protocol.lose_connection()
        except AttributeError:  # in case the connection was lost and the state is set by this event
            pass

    def send_cmd(self, cmd: ABDeviceCommand):
        error = DeviceShutdownError("Cannot send commands in Shutdown state!")
        self.device.log.error(f"{str(error)}")
        raise error

    def new_state(self, state, *args, **kwargs):
        pass


class Busy(DeviceState):
    def __init__(self, device, condition, waitcommand, *args, **kwargs):
        super().__init__(device, *args, **kwargs)
        self.condition = condition
        self._ready_for_urgent_command = False
        self.waitcommand = waitcommand
        self._accept_state = False
        self._defer_result = None

    def _run_next_urgent_cmd(self):
        try:
            parameters = self.device.cmd_queue[0].parameters
            if (parameters.urgent or parameters.run_while_device_busy) and self._ready_for_urgent_command:
                cmd = self.device.cmd_queue.pop(0)
                self._ready_for_urgent_command = False
                self.device.execute_cmd(cmd)
        except IndexError:
            pass

    def _ready(self):
        try:
            self._defer_result.callback(None)
        except AttributeError:
            self._ready_for_urgent_command = True
            self._run_next_urgent_cmd()

    def handle_success(self, result):
        cmd = result.command
        if cmd == self.waitcommand:
            if self._ready_for_urgent_command:  # meaning we are not waiting for a commands reply, if we are, we have to wait until it's success is handled
                self._accept_state = True
                self._ready_for_urgent_command = False
                return super().handle_success(result)
            else:
                def accept_and_return_result(_):
                    self._accept_state = True
                    return result
                self._defer_result = defer.Deferred().addCallback(accept_and_return_result).addCallback(super().handle_success)
                return self._defer_result
        else:
            return super().handle_success(result)

    def enter(self):
        self.device.log.info(f"Waiting for {self.condition}")
        self.device.conditionhandler.add_condition(self.condition, self.waitcommand.deferred_result)
        self._ready()

    def new_state(self, state, *args, **kwargs):
        if isinstance(state, (Shutdown, Error, Stopped)) and not self._accept_state:
            self.waitcommand.deferred_result.errback(state)
            self.device.conditionhandler.remove_deferred_for_condition(self.waitcommand.deferred_result, self.condition)
        elif isinstance(state, Ready) and not self._accept_state:
            self._ready()
            return
        super().new_state(state)

    def send_cmd(self, cmd: ABDeviceCommand):
        super().send_cmd(cmd)
        self._run_next_urgent_cmd()


class Waiting(Busy):
    pass
