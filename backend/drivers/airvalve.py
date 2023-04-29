from .two_way_valve_base import BaseDevice, SinglechannelBaseDevice, CommandParameterFactory, parser
import re


class Device(SinglechannelBaseDevice, BaseDevice):
    replies_commands = False
    log_name = "Airvalve"
    command_parameter_factory = CommandParameterFactory(command_execution_time=.1)
    parser_parameter_factory = parser.ParserParameterFactory(parserclass=parser.SuccessParser)
    delimiter = "\n"

    commands = {
        "OPEN": ["AIRVALVE_OPEN"],
        "CLOSE": ["AIRVALVE_CLOSE"],
    }

    def cmd_string(self, command_parameters: CommandParameterFactory) -> str:
        return command_parameters.commandstring

    def initial_commands(self):
        pass

    def final_commands(self):
        pass

    def handle_event(self, match: re.Match) -> None:
        pass

    def _set_isopen(self, result, isopen):
        self.is_open = isopen
        return result

    def open(self, **kwargs):
        return self.write("OPEN").deferred_result.addCallback(self._set_isopen, True)

    def close(self, **kwargs):
        return self.write("CLOSE").deferred_result.addCallback(self._set_isopen, False)
