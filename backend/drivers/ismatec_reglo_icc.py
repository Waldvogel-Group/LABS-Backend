import re
from twisted.internet import defer

from backend.conditions.conditions import ObservableEqualsValueCondition
from backend.combined_observables import MathExpression
from .pump_base import BaseDevice, MultichannelBaseDevice, commandstate, CommandParameterFactory


class Device(BaseDevice, MultichannelBaseDevice):
    delimiter = "\r\n"
    reply_to_state = {"*": commandstate.Success, "#": commandstate.Fail}
    event_patterns = [
        r"\^(?P<event_code>U)(?P<channel>[0-9])\|(?P<state_code>[A-E]+)\|"
        r"(?P<remaining_time_broken>[0-9]+)\|(?P<dosed_volume>[0-9]+)\|"
        r"(?P<remaining_cycles>[0-9]+)",
        r"\^(?P<event_code>X)(?P<channel>[0-9])\|(?P<reason>[AB123]+)",
    ]
    replies_commands = True
    log_name = "Ismatec Reglo ICC"

    command_parameter_factory = CommandParameterFactory(inter_command_time=0)

    commands = {
        # manual: http://www.ismatec.com/images/pdf/manuals/14-036_E_ISMATEC_REGLO_ICC_ENGLISH_REV.%20C.pdf

        # COMMUNICATIONS MANAGEMENT

        # Set Device Address
        "SET_ADDRESS": ["@"],
        # Get an integer representing whether (1) or not (0) channel addressing
        # is enabled.
        "GET_STATUS_CHANNEL_ADRESSING": ["~"],
        # Set whether channel messaging is enabled (1) or not enabled (0).
        "SET_STATUS_CHANNEL_ADRESSING": ["~"],
        # Get an integer representing whether (1) or not (0) event messages
        # are enabled.
        "GET_STATUS_ASYNCHRONOUS_COMMUNICATION": ["xE", r"(?P<state>.*)"],
        # Set whether event messages are enabled (1) or not enabled (0).
        "SET_STATUS_ASYNCHRONOUS_COMMUNICATION": ["xE"],
        # Get an integer representing the version of the _serial protocol.
        "GET_SERIAL_VERSION": ["x!"],

        # PUMP DRIVE

        # Start Pump (Response (-) channel setting(s) are not correct
        # or unachievable.)
        "START": ["H"],
        # Stop pumping
        "STOP": ["I"],
        # Pause pumping (STOP in RPM or flow rate mode).
        "PAUSE": ["xI"],
        # Get pump direction.
        "GET_DIRECTION": ["xD"],
        # Set rotation direction to clockwise.
        "CLOCKWISE": ["J"],
        # Set rotation direction to counter-clockwise.
        "COUNTERCLOCKWISE": ["K"],
        # Get information about the type of error, see manual for details
        "GET_ERROR": ["xe"],

        # OPERATIONAL MODES AND SETTINGS

        # Get the current channel or pump mode. L = RPM, M = Flow Rate,
        # O = Volume (at Rate), G = Volume (over Time), Q = Volume+Pause,
        # N = Time, P = Time+Pause
        "GET_MODE": ["xM"],
        # Set pump/channel to RPM mode.
        "SET_MODE_RPM": ["L"],
        # Set pump/channel to Flow Rate mode.
        "SET_MODE_FLOWRATE": ["M"],
        # Set pump/channel to Volume (at rate) mode.
        "SET_MODE_VOL_AT_RATE": ["O"],
        # Set pump/channel to Volume (over time) mode.
        "SET_MODE_VOL_OVER_TIME": ["G"],
        # Set pump/channel to Volume + Pause mode.
        "SET_MODE_VOL_PAUSE": ["Q"],
        # Set pump/channel to Time mode.
        "SET_MODE_TIME": ["N"],
        # Set pump/channel to Time + Pause mode.
        "SET_MODE_TIME_PAUSE": ["P"],
        # Get flow rate from RPM (S) or flow rate
        # (f) when mode is not RPM  or flow rate.
        "GET_RATE": ["xf"],
        # Set RPM flow rate not in RPM or flow rate mode Discrete Type 3.
        "SET_RATE": ["xf"],
        # Gets the current speed setting in RPM.
        "GET_SPEED": ["S"],
        # RPM mode flow rate setting (0.01 RPM) Discrete Type 3.
        "SET_SPEED": ["S"],
        # Get current volume/time flow rate (mL/min).
        "GET_VOL_RATE": ["f", r"(?P<rate>\d+E[+-]\d+)"],
        # Set RPM flow rate in volume/time mode (mL/min) Volume Type 2.
        "SET_VOL_RATE": ["f", r"(?P<rate>\d+E[+-]\d+)"],
        # Get the current setting for volume in mL.
        "GET_TARGET_VOL": ["v", r"(?P<volume>\d+E[+-]\d+)"],
        # Set the current setting for volume in mL. Volume Type 2.
        "SET_TARGET_VOL": ["v", r"(?P<volume>\d+E[+-]\d+)"],
        # Get the current pump run time.
        "GET_RUN_TIME": ["xT"],
        # Set current pump run time using Time Type 2.
        "SET_RUN_TIME": ["xT"],
        # Get pumping pause time.
        "GET_PAUSE_TIME": ["xP"],
        # Set pumping pause time using Time Type 2.
        "SET_PAUSE_TIME": ["xP"],
        # Get pump cycle count.
        "GET_CYCLE_COUNT": ["\""],
        # Set pump cycle count Discrete Type 2.
        "SET_CYCLE_COUNT": ["\""],
        # Max flow rate achievable with current settings mL/min.
        "GET_MAX_VOL_RATE": ["?"],
        # Max flow rate achievable with current settings using calibration.
        "GET_MAX_VOL_RATE_CAL": ["!"],
        # Get time to dispense at a given volume at a given mL/min flow rate.
        # Vol, Volume Type 2; flow rate, Volume Type 2.
        "GET_TIME_FROM_VOL_VOL_RATE": ["xv"],
        # Get time to dispense at a given volume at a given RPM. mL,
        # Volume Type 2; flow rate, Discrete Type 3.
        "GET_TIME_FROM_VOL_RPM": ["xw"],
        # CONFIGURATION
        # Get the current tubing inside diameter in mm. 2 decimal places
        # are returned.
        "GET_DIAMETER": ["+"],
        # Set tubing inside diameter using Discrete Type 2.
        "SET_DIAMETER": ["+"],
        # Get the current backsteps setting.
        "GET_BACKSTEPS_SETTING": ["%"],
        # Set the current backsteps setting using Discrete Type 2.
        "SET_BACKSTEPS_SETTING": ["%"],
        # Resets all user configurable data to default values.
        "RESET_CONFIG": ["0"],

        # CALIBRATION

        # Get direction flow for calibration.
        "CAL_GET_DIR_FLOW": ["xR"],
        # Set direction flow for calibration J or K using DIRECTION format.
        "CAL_SET_DIR_FLOW": ["xR"],
        # Get the target volume to pump for calibrating, mL.
        "CAL_GET_TARGET_VOL": ["xU"],
        # Set the target volume to pump for calibrating using Volume Type 2.
        "CAL_SET_TARGET_VOL": ["xU"],
        # Set actual volume measured during calibration, mL Volume Type 2.
        "CAL_SET_ACTUAL_VOL": ["xV"],
        "CAL_GET_TIME": ["xW"],  # Get the current calibration time.
        # Set the current calibration time using Time Type 2.
        "CAL_SET_TIME": ["xW"],
        # Get the channel run time since last calibration.
        "CAL_GET_RUN_SINCE_CAL": ["xX"],
        # Start calibration on a channel(s).
        "CAL_START": ["xY"],
        # Cancel calibration.
        "CAL_CANCEL": ["xZ"],

        # SYSTEM

        # Returns the pump firmware version.
        "GET_FW_VERSION": ["(", r"(?P<firmware_version>\d+)"],
        # Change f roller step volume for a particular roller count and tubing
        # size using roller count (6,8,12), Discrete Type 1; index of the tubing
        # diameter (see Table 1), Discrete Type 1; RSV. Volume Type 2.
        "SET_ROLLER_STEP_VOL": ["xt"],
        # Save set roller step settings.
        "SAVE_ROLLER_STEP_SETTINGS": ["xs"],
        # Reset roller step volume table to defaults.
        "RESET_ROLLER_STEP_VOL": ["xu"],
        # Set pump name for display under remote control–String.
        "SET_PUMP_NAME": ["xN"],
        # Get pump _serial number.
        "GET_SERIALNUMBER": ["xS"],
        # Set pump _serial number–String.
        "SET_SERIALNUMBER_STRING": ["xS"],
        # Get the current pump language.
        "GET_LANGUAGE": ["xL"],
        # Set the current pump language-Language.
        "SET_LANGUAGE": ["xL"],
        # Get number of pump channels.
        "GET_CHANNELS": ["xA", r"(?P<channelcount>\d)"],
        # Configure number of pump channels. Discrete Type 2.
        "SET_CHANNELS": ["xA"],
        # Get number of rollers for channel.
        "GET_ROLLERS": ["xB"],
        # Set number of rollers for channel. Discrete Type 2.
        "SET_ROLLERS": ["xB"],
        # Get total number of revolutions since last reset.
        "GET_REV_SINCE_RESET": ["xC"],
        # Get channel total volume pumped since last reset, mL.
        "GET_VOL_SINCE_RESET": ["xG"],
        # Get total time pumped for a channel since last reset.
        "GET_TIME_SINCE_RESET": ["xJ"],
        # Set control from the pump user interface.
        "SET_MANUAL_CONTROL_ON": ["A"],
        # Disable pump user interface.
        "SET_MANUAL_CONTROL_OFF": ["B"],
        # Write numbers to the pump to display while under external
        # control–String (<17 characters).
        "SET_DISPLAY_NUMBERS": ["D"],
        # Write letters to the pump to display while under external
        # control–String(<17 characters).
        "SET_DISPLAY_LETTERS": ["DA"],
        # Returns whether the pump is currently running or not.
        "GET_RUNNING": ["E"],
        # Returns the following fields, each separated by a space:
        # Pump model description: A text field describing the model of pump.
        # This description may contain spaces.
        # Pump software version: The version of software currently running
        # in the pump.
        # Pump head model type code: A code describing the type of pump head
        # installed. The first digit represents the number of channels for the
        # pump, and the second 2 digits represent the number of rollers.
        # XX if channels do not have the same number of rollers.
        "GET_DATA": ["#"],
        # Returns the pump head model type code–A 4 digit code indicating the
        # ID number of the pump head. The first two digits represent the number
        # of channels on the head, and the second 2 digits represent the number
        # of rollers.
        "GET_HEAD_MODEL_TYPE": [")"],
        # Sets the pump head model type code –An up-to 4 digit code setting the
        # ID number of the pump head. The first two digits encode the number of
        # channels on the head, the second two digits encode the number of
        # rollers on the head. This command_name sets all roller counts to the
        # same state. To individually set roller counts for each channel, use
        # the non-legacy command_name designed for this operation.
        # Discrete Type 2.
        "SET_HEAD_MODEL_TYPE": [")"],
        # Get the current setting for pump time in 1/10 second.
        "GET_PUMP_TIME": ["V"],
        # Set the current setting for pump time in 1/10 second. Discrete Type 2.
        "SET_PUMP_TIME": ["V"],
        # Set the current run time setting for dispensing in minutes.
        # Discrete Type 5.
        "SET_RUN_TIME_DISPENSING_MIN": ["VM"],
        # Set the current run time setting for dispensing in hours.
        # Discrete Type 5.
        "SET_RUN_TIME_DISPENSING_H": ["VH"],
        # Get the low order roller steps. The total number of roller steps which
        # are dispensed during an operation is computed as:[(u*65536]+(U)].
        "GET_LOW_ORDER_ROLLER_STEPS": ["U"],
        # Set the low order roller steps. Discrete Type 6.
        "SET_LOW_ORDER_ROLLER_STEPS": ["U"],
        # Get the high order roller steps. The total number of roller steps
        # which are dispensed during an operation is computed as:
        # [(u*65536]+(U)].
        "GET_HIGH_ORDER_ROLLER_STEPS": ["u"],
        # Set the high order roller steps. Discrete Type 6.
        "SET_HIGH_ORDER_ROLLER_STEPS": ["u"],
        # Get the current roller step volume based on the current calibration,
        # tubing diameter and roller count. If no calibration has been performed
        # the default volume is returned.
        "GET_ROLLER_STEP_VOL_CAL": ["r"],
        # Set the calibrated roller step volume to use for this pump or channel.
        # This state is used as the calibrated state and is overwritten by
        # subsequent calibrations and reset by changing tubing diameter.
        # Volume Type 2.
        "SET_ROLLER_STEP_VOL_CAL": ["r"],
        # Reset the pump to discard calibration data, use default roller
        # step volume.
        "RESET_CAL_DATA": ["000000"],
        # Get the current setting for pause time in 1/10 second.
        "GET_SETTING_PAUSE_TIME": ["T"],
        # Set the current setting for pause time in 1/10 second. Discrete Type 2.
        "SET_SETTING_PAUSE_TIME": ["T"],
        # Set the current setting for pause time in minutes. Discrete Type 5.
        "SET_SETTING_PAUSE_TIME_MIN": ["TM"],
        # Set the current setting for pause time in hours. Discrete Type 5.
        "SET_SETTING_PAUSE_TIME_H": ["TH"],
        # Get the total volume dispensed since the last reset in μL, mL or liters.
        "GET_TOTAL_VOL_SINCE_RESET": [":"],
        # Saves the current pump settings values to memory.
        "SAVE_TO_MEM": ["*"],
        # Get the current state of the foot switch.
        "GET_STATE_FOOT_SWITCH": ["C"],
    }

    def cmd_string(self, command_parameters: CommandParameterFactory) -> str:
        channel = command_parameters.channel
        try:
            value = command_parameters.command_values["value"]
        except KeyError:
            value = ""
        else:
            if isinstance(value, list):
                value = "|".join(value)
        return f"{channel}{command_parameters.commandstring}{value}"

    def initial_commands(self):
        self.write("SET_ADDRESS", channel="", command_values={"value": 1})
        self.write("SET_STATUS_CHANNEL_ADRESSING",
                   channel=1, command_values={"value": 1})
        self.write("CLOCKWISE", channel=0)
        self.stop_pumping()
        super().initial_commands()
        self.start_events()

    def final_commands(self):
        self.stop_pumping()

    def _get_channels(self) -> defer.Deferred:
        return self.query("GET_CHANNELS", channel=0)

    def handle_event(self, match: re.Match) -> None:
        try:
            log = self.channels[int(match.group("channel"))].log
        except IndexError:
            log = self.log
        if match.group("event_code") == "X":
            reason = {"A": "Pumping finished.",
                      "B": "Pumping for calibration finished.",
                      "1": "Pumping stopped manually.",
                      "2": "Temperature to high.",
                      "3": "Voltage to high."}[match.group("reason")]
            log.info("Stopped pumping: {reason}", reason=reason)
        elif match.group("event_code") == "U":
            log.info("Updated parameters: {parameters}",
                     parameters=match.groupdict())
            

    def dispense(self, rate, volume, **kwargs):
        if float(volume) == 0:
            return
        self.write("SET_MODE_VOL_AT_RATE", **kwargs)
        if float(rate) < 0 or float(volume) < 0:
            self.write("COUNTERCLOCKWISE", **kwargs)
        else:
            self.write("CLOCKWISE", **kwargs)
        self.write("SET_VOL_RATE", command_values={
                   "value": self._volume2(rate)}, **kwargs)
        self.write("SET_TARGET_VOL", command_values={
                   "value": self._volume2(volume)}, **kwargs)

        observable = self.channel_acting or self
        remaining_time = MathExpression(
            observable, "remaining_time", f"abs(60*({volume}-(dosed_volume/1000))/{rate})")

        def start_time(result):
            remaining_time.start()
            return result

        self.write("START", **kwargs).deferred_result.addCallback(start_time)

        def stop_remaining_time(result):
            remaining_time.stop()
            return result
        self.busy(ObservableEqualsValueCondition("dispense finished", observable,
                  "event_code", "X")).deferred_result.addBoth(stop_remaining_time)

    def continuous_flow(self, rate, **kwargs):
        self.write("SET_MODE_FLOWRATE", **kwargs)
        if float(rate) < 0:
            self.write("COUNTERCLOCKWISE", **kwargs)
        else:
            self.write("CLOCKWISE", **kwargs)
        self.write("SET_VOL_RATE", command_values={
                   "value": self._volume2(rate)}, **kwargs)
        self.write("START", **kwargs)

    def stop_pumping(self, **kwargs):
        if self.channel_acting is None:
            self.write("STOP", channel=0, **kwargs)
        else:
            self.write("STOP", **kwargs)

    def start_events(self):
        return self.write(
            "SET_STATUS_ASYNCHRONOUS_COMMUNICATION",
            command_values={"value": 1})

    def stop_events(self):
        return self.write(
            "SET_STATUS_ASYNCHRONOUS_COMMUNICATION",
            command_values={"value": 0})

    @staticmethod
    def _volume2(number):
        """
        convert number to "volume type 2"
        :param number:
        :return: number converted to "volume type 2"
        """
        number = float(number)
        number = f"{abs(number):.3e}"
        number = number[0] + number[2:5] + number[-3] + number[-1]
        return number

    @staticmethod
    def _volume1(number):
        """
        convert number to "volume type 1"
        :param number:
        :return: number converted to "volume type 1"
        """
        number = f"{abs(number):.3e}"
        number = number[0] + number[2:5] + "E" + number[-3] + number[-1]
        return number

    @staticmethod
    def _discrete2(number):
        """
        convert number to "discrete type 2"
        :param number:
        :return: number converted to "discrete type 2"
        """
        assert number < 10
        whole, decimals = f"{number:.2f}".split(".")
        return f"{int(whole + decimals):0>4}"
