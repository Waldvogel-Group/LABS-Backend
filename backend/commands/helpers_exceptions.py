from enum import Enum

from backend.commands.results import Result


class CommandAction(Enum):
    RETRY = "retry"
    FAIL = "fail"


class CommandError(Exception, Result):
    """Baseclass for all errors that commands take as their temp_result."""
    errorcode = ""

    def __init__(self, reply: Result, *args, msg: str = None, **kwargs):
        self.command = reply.command
        self.time = reply.time
        self.command = None  # set by command
        self.parameters = reply.parameters if reply is not None else None
        if not msg:
            msg = ""
        self.line = self.errorcode + " " + msg
        super().__init__(self.line, *args, **kwargs)


class CommandResponseError(CommandError):
    """Raised when a device didn't respond as expected"""
    errorcode = "Received an unexpected response."


class CommandRetryError(CommandError):
    """Raised when the maximal number of retries is reached"""
    errorcode = "Command reached maximum number of retries."


class CommandTimeoutError(CommandError):
    """Raised when the maximal number of retries is reached"""
    errorcode = "Command timed out."


class CommandErrorError(CommandError):
    """Raised when the device actually responded with an error"""
    errorcode = "Received error from device:"

    def __init__(self, *args, match=None, **kwargs):
        if match:
            msg = match.string
            self.error_details = match.groupdict()
            super().__init__(*args, msg=msg, **kwargs)
        else:
            super().__init__(*args, **kwargs)


class CommandSeriesError(CommandError):
    """Raised when a CommandSeries fails, due to a Command failing"""
    errorcode = "CommandSeries failed"


class BaseParameterFactoryClass:
    def __call__(self, **kwargs):
        """Makes parameters easily updatable by calling them"""
        new_parameters = self.__dict__.copy()
        try:
            old_kwargs = new_parameters.pop("kwargs")
        except KeyError:
            pass
        else:
            new_parameters.update(old_kwargs)
        for key, value in kwargs.items():
            new_parameters[key] = value
        return type(self)(**new_parameters)
