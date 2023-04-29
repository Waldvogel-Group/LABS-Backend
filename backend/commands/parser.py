from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Tuple, Type, Pattern

from twisted.internet import reactor

from backend.commands import commandstate
from backend.commands.helpers_exceptions import CommandError
from backend.commands.results import Result
from backend.commands.helpers_exceptions import BaseParameterFactoryClass


class BaseParser(ABC):
    def __init__(self, command, *args, **kwargs):
        self.command = command  # set by Command

    @abstractmethod
    def __call__(self, reply: Result):
        """
        Parse the reply and return the appropriate Result or CommandError subclass object and a CommandState subclass.
        :param reply: Result to parse
        :return: Result or CommandError subclass object and a subclass of commandstate.CommandState to set on command
        """
        raise NotImplementedError


class REParser(BaseParser):
    def __init__(self, command, pattern: Pattern, expected_values: dict = None, **kwargs):
        super().__init__(command)
        self.pattern = pattern

        if expected_values is None:
            expected_values = {}
        self.expected_values = expected_values

    def __call__(self, reply: Result) -> Tuple[Result | CommandError, Type[commandstate.CommandState]]:
        try:
            reply.parameters = self.pattern.match(str(reply)).groupdict()
        except AttributeError:
            temp_result = commandstate.CommandResponseError(reply=reply,
                                                            msg=f"{reply} doesn't match {self.pattern.pattern}.")
            return temp_result, commandstate.Retry
        else:
            self.command.device.log.info("{command.parameters.commandstring} returned with parameters: {parameters}",
                                         command=self.command, parameters=reply.parameters)
            for key, value in self.expected_values.items():
                try:
                    if not str(value) == reply.parameters[key]:
                        temp_result = commandstate.CommandResponseError(
                            reply=reply,
                            msg=("At least one parameter value of the reply was not as expected. "
                                 f"{reply.parameters[key]} is not {value}")
                        )
                        return temp_result, commandstate.Retry
                except KeyError:
                    temp_result = commandstate.CommandResponseError(
                        reply=reply,
                        msg=f"Expected parameter {key} is not in {reply}.")
                    return temp_result, commandstate.Retry
            temp_result = reply
            return temp_result, commandstate.Success


class CommandReplyParser(BaseParser):
    def __init__(self, command, reply_to_state: dict = None, **kwargs):
        super().__init__(command)
        self.reply_to_state = reply_to_state or self.command.device.reply_to_state

    def __call__(self, reply: Result) -> Tuple[Result | CommandError, Type[commandstate.CommandState]]:
        try:
            state = self.reply_to_state[str(reply)]
        except KeyError:
            state = commandstate.Retry
            temp_result = commandstate.CommandResponseError(
                reply=reply,
                msg=f"Unexpected reply. {reply} is not in {self.reply_to_state}")
        else:
            if state == commandstate.Success:
                temp_result = reply
            elif state == commandstate.Retry:
                temp_result = commandstate.CommandErrorError(reply=reply, msg=f"Device responded with {reply}")
            else:
                temp_result = commandstate.CommandResponseError(reply=reply, msg=f"Device responded with {reply}")
        return temp_result, state


class SuccessParser(BaseParser):
    def __call__(self, reply: Result) -> Tuple[Result, Type[commandstate.CommandState]]:
        return reply, commandstate.Success


class ParserParameterFactory(BaseParameterFactoryClass):
    def __init__(self, parserclass: Type[BaseParser] = CommandReplyParser, **kwargs):
        self.parserclass = parserclass
        self.kwargs = kwargs

