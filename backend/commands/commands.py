# -*- test-case-name: backend.test.test_commands -*-

from abc import ABC, abstractmethod
from contextlib import ContextDecorator
from typing import Optional, Type, Any

from twisted.internet import defer
from twisted.internet import reactor

from backend.commands import commandstate, parser
from backend.commands.results import Result
from backend.commands.helpers_exceptions import (CommandAction,
    BaseParameterFactoryClass, CommandError, CommandSeriesError)
from backend.helpers_exceptions import StateMachineMixIn, WrongStateError
from backend.devices import devicestate

class DeviceCommandParameterFactory(BaseParameterFactoryClass):
    def __init__(
            self,
            retries: int = 3,
            inter_command_time: float = .1,
            on_error: CommandAction = CommandAction.RETRY,
            urgent: bool = False,
            run_while_device_busy: bool = False,
            channel: Optional[int] = None,
            devicestate_while_executing: \
                devicestate.DeviceState | Type[devicestate.DeviceState] \
                = devicestate.NotReady,
            next_devicestate: \
                devicestate.DeviceState | Type[devicestate.DeviceState] \
                = devicestate.Ready,
            **kwargs
    ):
        self.retries = retries
        self.inter_command_time = inter_command_time
        self.on_error = on_error
        self.urgent = urgent
        self.run_while_device_busy = run_while_device_busy
        self.channel = channel
        self.devicestate_while_executing = devicestate_while_executing
        self.next_devicestate = next_devicestate


class CommandParameterFactory(DeviceCommandParameterFactory):
    def __init__(
            self,
            commandstring: str = "",
            timeout: float = 2.5,
            command_execution_time: float = .5,  
            # How long does it take until the command is executed if no response
            # is expected.
            query: bool = False,
            on_timeout: CommandAction = CommandAction.FAIL,
            command_values: dict[Any, Any] = None,
            **kwargs
    ):
        self.commandstring = commandstring
        self.timeout = timeout
        self.command_execution_time = command_execution_time
        self.on_timeout = on_timeout
        self.command_values = command_values if command_values is not None else {}
        self.query = query
        super().__init__(**kwargs)


class IProtocolCommand(ABC):
    bytestring: Optional[bytes] = None
    parameters: Optional[CommandParameterFactory] = None


class ABDeviceCommand(StateMachineMixIn, ABC):
    deferred_result: defer.Deferred

    def __init__(
            self,
            device,
            command_parameter: DeviceCommandParameterFactory = \
                DeviceCommandParameterFactory(),
            **kwargs):
        self.device = device
        self.log = self.device.log
        self.parameters = command_parameter(**kwargs)
        super().__init__(initial_stateclass=commandstate.NotSent)

    @abstractmethod
    def execute(self):
        raise NotImplementedError

    @abstractmethod
    def cancel(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def temp_result(self) -> Result:
        raise NotImplementedError

    @temp_result.setter
    @abstractmethod
    def temp_result(self, result: Result):
        raise NotImplementedError


class Command(ABDeviceCommand, IProtocolCommand):
    def __init__(self, device, command_parameter: CommandParameterFactory = CommandParameterFactory(),
                 parser_parameter: parser.ParserParameterFactory = parser.ParserParameterFactory()):
        super().__init__(device, command_parameter)
        self.bytestring = command_parameter.commandstring.encode()
        self.parser = parser_parameter.parserclass(self, **parser_parameter.kwargs)
        self.timer = None
        self.fail_count = 0
        self._result = None
        self.time = None
        self.response_time = None
        self.result = None
        self.deferred_execution = defer.Deferred()
        self.deferred_result = defer.Deferred()
        self.deferred_result.addBoth(self._set_result)

    def __repr__(self):
        return f"{self.__class__.__name__} {self.parameters.commandstring}"

    def execute(self):
        self.device.protocol.write_command(self)
        self.state = commandstate.Sent
        deferred, self.deferred_execution = self.deferred_execution, defer.Deferred()
        deferred.callback(None)

    def cancel(self):
        self.deferred_result.cancel()
        self.state = commandstate.Cancelled

    def _set_result(self, result):
        self.result = result
        return result

    @property
    def temp_result(self):
        return self._result

    @temp_result.setter
    def temp_result(self, result: Result):
        if self.state == commandstate.NotSent:
            raise WrongStateError("Cannot set result before Command was Sent!")
        assert self.state is not commandstate.NotSent, "Cannot set temp_result before command was sent"
        try:
            self.timer.cancel()
            self.timer = None
        except AttributeError:
            pass
        self._result = result
        result.command = self
        self.response_time = result.time - self.time


class CommandSeries(ABDeviceCommand, ContextDecorator):
    def __init__(self, device, commandlist: list[ABDeviceCommand] = None,
                 command_parameter: DeviceCommandParameterFactory = DeviceCommandParameterFactory(retries=1)):
        self.commandlist = commandlist if commandlist is not None else []
        super().__init__(device, command_parameter)
        for cmd in self.commandlist:
            self.parameters.urgent = self.parameters.urgent or cmd.parameters.urgent
        self.cmd_counter = 0
        self.fail_count = 0
        self._cached_devicestate = None
        self.has_command_series = False
        self.parent_command_series = None
        self._temp_result = None
        self.deferred_result = defer.Deferred()

    def __repr__(self):
        return f"{self.__class__.__name__} {self.commandlist}"

    def __enter__(self):
        self._cached_devicestate = self.device.stateobject
        self.device.state = devicestate.CollectingCommands
        self.device.stateobject.commandseries = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for cmd in self.commandlist:
            self.parameters.urgent = self.parameters.urgent or cmd.parameters.urgent
        if self.parameters.urgent:
            for cmd in self.commandlist:
                cmd.parameters.urgent = True
        self.device.reuse_state_without_enter(self._cached_devicestate)
        self.device.send_cmd(self)

    def execute(self):
        for cmd in self.commandlist:
            if isinstance(cmd, CommandSeries):
                self.has_command_series = True
                cmd.parent_command_series = self
        if len(self.commandlist) > 0:
            return self.current_command.execute()
        else:
            self._temp_result = Result()
            self._temp_result.command = self
            reactor.callLater(self.parameters.inter_command_time, self.succeed)

    def cancel(self):
        for command in self.commandlist:
            command.cancel()
        self.state = commandstate.Cancelled
        self.deferred_result.cancel()

    @property
    def current_command(self) -> ABDeviceCommand:
        return self.commandlist[self.cmd_counter]

    @property
    def parser(self):
        return self.current_command.parser

    @StateMachineMixIn.state.setter
    def state(self, state_or_stateclass):
        if isinstance(state_or_stateclass, commandstate.CommandState):
            stateclass = type(state_or_stateclass)
        else:
            stateclass = state_or_stateclass
        if stateclass is commandstate.Success:
            if self.has_command_series and isinstance(self.current_command, CommandSeries):
                self.current_command.state = state_or_stateclass
            else:
                self.next_cmd()
        elif stateclass is commandstate.Retry:
            if isinstance(stateclass(self.current_command), commandstate.Fail):
                self._retry()
            else:
                self.current_command.fail_count -= 1  # because it was increased by the if statement above
                self.current_command.state = state_or_stateclass
        elif stateclass is commandstate.Cancelled:
            self.stateobject.new_state(stateclass(self))
        else:
            self.current_command.state = state_or_stateclass

    @property
    def temp_result(self):
        return self._temp_result

    @temp_result.setter
    def temp_result(self, result: Result | CommandError):
        self.current_command.temp_result = result
        own_result = Result(f"{[(command, str(command.temp_result)) for command in self.commandlist]}")
        if isinstance(result, CommandError):
            self._temp_result = CommandSeriesError(own_result)
        else:
            self._temp_result = own_result
            self._temp_result.command = self

    def next_cmd(self):
        if self.cmd_counter < len(self.commandlist)-1:
            self.cmd_counter += 1
            self.device.execute_cmd(self)
        elif self.parent_command_series is not None:
            self.parent_command_series.next_cmd()
        else:
            self.succeed()

    def _retry(self):
        self.fail_count += 1
        if self.fail_count > self.parameters.retries:
            return self.fail()
        else:
            self.log.info(f"last executed command failed, retrying {self}")
            self.cmd_counter = 0
            for cmd in self.commandlist:
                cmd.fail_count = 0
            self.device.execute_cmd(self)

    def succeed(self):
        for command in self.commandlist:
            if self.has_command_series and isinstance(command, CommandSeries):
                command.succeed()
            else:
                command.state = commandstate.Success
        self.stateobject.new_state(commandstate.Success(self))

    def fail(self):
        self.log.error(f"{self} failed.")
        self.stateobject.new_state(commandstate.Fail(self))
        for i in range(0, self.cmd_counter):
            cmd = self.commandlist[i]
            if self.has_command_series and isinstance(cmd, CommandSeries):
                cmd.succeed()
            else:
                cmd.state = commandstate.Success
        if self.has_command_series and isinstance(self.current_command, CommandSeries):
            self.current_command.fail()
        else:
            self.current_command.state = commandstate.Fail


class RepeatedCommand(ABDeviceCommand):
    def __init__(self, device, write_function, command_name: str, interval: float, stop_condition = None, **kwargs):
        self.command_name = command_name
        self.interval = interval
        self.last_command = None
        self._temp_result = None

        def set_result(result):
            self.temp_result = result
            result.command = self
            return result
        
        self.deferred_result = defer.Deferred().addCallback(set_result)

        def stop_running(result):
            self.stop_running()
            return result
        self.deferred_stop = defer.Deferred().addCallback(stop_running)
        parameter_kwargs = kwargs.copy()
        parameter_kwargs["inter_command_time"] = 0.001
        super().__init__(device, **parameter_kwargs)
        self.write_function = write_function
        self._continue_running = False
        self.stop_condition = stop_condition
        kwargs["urgent"] = True
        self.kwargs = kwargs

    def __repr__(self):
        return f"Repeated Command '{self.command_name}' every {self.interval} s"

    def _next_iteration(self, result):
        reactor.callLater(self.interval, self._run_command)
        self.last_command = result.command
        return result

    def _run_command(self):
        if self._continue_running:
            self.write_function(self.command_name, **self.kwargs).deferred_result.addCallback(self._next_iteration)

    def stop_running(self):
        self.log.info(f"Stopping repeated command {self}")
        self._continue_running = False
        if self.stop_condition is not None:
            try:
                self.device.conditionhandler.remove_deferred_for_condition(self.deferred_stop, self.stop_condition)
            except KeyError:
                pass
            except ValueError:
                pass

    def execute(self):
        self._continue_running = True
        if self.stop_condition:
            self.device.conditionhandler.add_condition(self.stop_condition, self.deferred_stop)
        reactor.callLater(0, self._run_command)
        self.deferred_result.callback(Result())

    def cancel(self):
        raise NotImplementedError

    @property
    def temp_result(self):
        try:
            return self.last_command.temp_result
        except AttributeError:
            return self._temp_result

    @temp_result.setter
    def temp_result(self, result: Result):
        self._temp_result = result


class WaitCommand(ABDeviceCommand):
    def __init__(self, device, condition, *args,
                 command_parameter: DeviceCommandParameterFactory = DeviceCommandParameterFactory(
                     devicestate_while_executing=devicestate.Waiting),
                 **kwargs):
        super().__init__(device, command_parameter, *args, **kwargs)
        self.condition = condition
        self._temp_result = None

        self.deferred_result = defer.Deferred().addBoth(self._set_result)
        self.deferred_execution = defer.Deferred()
        self.parameters.devicestate_while_executing = self.parameters.devicestate_while_executing(
            self.device, self.condition, self)

    def _set_result(self, result):
        self.result = self._temp_result = Result()
        self.result.command = self
        return self.result

    def execute(self):
        self.deferred_execution.callback(None)

    def cancel(self):
        raise NotImplementedError

    @property
    def temp_result(self) -> Result:
        return self._temp_result

    @temp_result.setter
    def temp_result(self, result):
        self._temp_result = result
        result.command = self