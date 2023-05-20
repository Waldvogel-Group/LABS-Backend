from .fraction_collector_base import BaseDevice, SinglechannelBaseDevice, CommandParameterFactory
from backend.commands.parser import ParserParameterFactory, SuccessParser
import re


class Device(BaseDevice, SinglechannelBaseDevice):
    command_parameter_factory = CommandParameterFactory(command_execution_time=1.5)
    parser_parameter_factory = ParserParameterFactory(parserclass=SuccessParser)
    serial_parameters = {"baudrate": 2400, "parity": "O"}
    replies_commands = False
    log_name = "Lambda Instruments Omnicoll"
    commands = {
        # manual: https://www.lambda-instruments.com/fileadmin/user_upload/PDF/OMNICOLL/LAMBDA-OMNICOLL-fraction-collector-and-sampler-manual.pdf
        ### COMMON COMMANDS ###
        "START": ["r"],  # start (run)
        "ACTIVATE_REMOTE": ["e"],  # activates remote control of the collector (front panel deactivated)
        "ACTIVATE_LOCAL": ["g"],  # activates local mode (front panel activated)
        "STOP": ["s"],  # stop
        "STEP_FORWARD": ["f"],  # step forward
        "STEP_BACK": ["b"],  # step back
        "STEP_IN_MV_DIRECTION": ["w"],
        # step in actual moving direction (depending on LINE or MEAN setting) [corresponds to pressing the STEP button]
        "STEP_NEXT_LINE": ["l"],  # step to next reply
        "HIGH_MODE": ["h"],
        # "high" mode, used for the collection of samples with a time interval between consecutive fractions
        "NORMAL_MODE": ["u"],  # "normal" mode
        "MODE_MEAN": ["m"],  # “MEAN” collection mode (meander or zigzag collection mode)
        "MODE_LINE": ["v"],  # “LINE” collection mode (collects fractions always from left to right)
        "MODE_ROW": ["i"],  # “ROW” collection mode, the collector moves only from row to row
        "SET_TIME_MINUTE_FRACTIONS": ["d"],  # unit setting – 0.1 minute step time setting (XXX.X)
        "SET_TIME_MINUTES": ["j"],  # unit setting – minute step time setting (XXXX)
        "OPEN_VALVE": ["o"],  # open valve
        "CLOSE_VALVE": ["c"],  # close valve
        "DIV_COEF_SETTING_ONE": ["a"],  # division coefficient setting “1”
        "DIV_COEF_SETTING_60TH": ["k"],  # division coefficient setting “1/60”
        "NUMBER_OF_PULSES": ["p"],  # number of pulses from pump or drop counter
        "COLLECTION_TIME_MINUTES_FRACTIONS": ["t"],  # collection time (in 0.1 minute steps)
        "COLLECTION_TIME_MINUTES": ["t"],  # collection time (in minute steps)
        "SET_PAUSE_TIME_MINUTES_FRACTIONS": ["q"],
        # pause time between two fractions (in 0.1 minute steps) (fraction collector automatically enters “high” mode)
        "SET_PAUSE_TIME_MINUTES": ["q"],
        # pause time between two fractions (in minute steps) (fraction collector automatically enters “high” mode)
        "NUMBER_OF_FRACTIONS": ["n"],  # number of fractions (fraction collector automatically enters “high” mode)
        "REQUEST_COLLECTION_TIME": ["G 0"],  # to request the fraction collector to send data to the PC
        "REQUEST_PULSE_SETTING": ["G 1"],  # to request the fraction collector to send data to the PC
        "REQUEST_PAUSE_TIME": ["G 2"],  # to request the fraction collector to send data to the PC
        "REQUEST_NUMBER_OF_FRACTIONS": ["G 3"],  # to request the fraction collector to send data to the PC
    }

    def __init__(self, *args, master="01", slave="02", **kwargs):
        self.master, self.slave = master, slave
        super().__init__(*args, **kwargs)

    def initial_commands(self):
        cmd_time = .1
        self.write("ACTIVATE_REMOTE", command_execution_time=cmd_time)
        self.write("NORMAL_MODE", command_execution_time=cmd_time)
        self.write("MODE_MEAN", command_execution_time=cmd_time)

    def final_commands(self):
        pass

    def handle_event(self, match: re.Match) -> None:
        pass

    def cmd_string(self, command_parameters: CommandParameterFactory) -> str:
        command = command_parameters.commandstring
        try:
            value = command_parameters.command_values["value"]
        except KeyError:
            value = ""
        return f"#{self.slave}{self.master}{command}{value}{self.generate_checksum(command, value)}"

    def generate_checksum(self, command, value):
        """
        Takes command_name and state. Returns checksum for use in _serial communication.
        :param command:
        :param value:
        :return: checksum
        """
        string = "#" + self.slave + self.master + command + value
        chk = 0
        for i in string:
            chk += ord(i)
        return str(hex(chk)[-2:]).upper()

    def next_fraction(self):
        self.write("STEP_IN_MV_DIRECTION")

    def previous_fraction(self):
        self.write("STEP_BACK")

    def reset_to_start(self):
        raise NotImplementedError("Please restart the device to reset it!")

    def next_line(self):
        self.write("STEP_NEXT_LINE", command_execution_time=10)