import re
from time import sleep
from backend.conditions.conditions import TimeCondition
from .pump_base import BaseDevice, SinglechannelBaseDevice, commandstate, CommandParameterFactory


class Device(BaseDevice, SinglechannelBaseDevice):
    receiving_delimiter = "/"
    sending_delimiter = ""
    reply_to_state = {"OK": commandstate.Success}
    replies_commands = True
    log_name = "Eldex Optos"

    commands = {
        # manual: https://drive.google.com/file/d/1TUQEOdOac2bR52FdJ7qrJ7ity_CL1cVq/view

        "START": ["RU"],  # Start the pump
        "STOP": ["ST"],  # Stop the pump
        "SET_VOL_RATE": ["SF"],  # Set flow rate in mL/min.
        "GET_VOL_RATE": ["RF", r"OK(?P<flowrate>\d{5})"],  # Get flow rate in mL/min.
        "GET_ID": ["ID", r"OK(?P<piston_diameter_code>[012])(?P<piston_stroke_code>[012])(?P<pump_material_code>[01])(?P<eprom_rev>\d{3})"],  # Get information on piston diameter (0=.093, 1=.125, 2=.250), piston stroke (0=.125, 1=.250, 2=.500), pump material (0=ss, 1=pk) and eprom revision.
        "GET_CURRENT_PRESSURE": ["RP", r"OK,(?P<pressure>\d{4})"],  # Reads the pump pressure.
        "SET_HIGH_PRESSURE_LIMIT": ["SH"],  # Set the high pressure limit.
        "SET_LOW_PRESSURE_LIMIT": ["SL"],  # Set the low pressure limit.
        "GET_HIGH_PRESSURE_LIMIT": ["RH", r"OK(?P<high_pressure_limit>\d{4})"],  # Read the high pressure limit.
        "GET_LOW_PRESSURE_LIMIT": ["LH", r"OK(?P<low_pressure_limit>\d{4})"],  # Read the low pressure limit.
        "SET_COMPRESSIBILITY_COMPENSATION": ["SC"],  # Sets the pump compressibility compensation
        "GET_COMPRESSIBILITY_COMPENSATION": ["RC", r"OK(?P<compressibility_compensation>\d{2})"],  # Reads the pump compressibility compensation.
        "SET_REFILL_RATE_FACTOR": ["SR"],  # Sets the pump refill rate factor (0=Full Out; 1=15:85; 2=30:70; 3=50:50; 4=70:30).
        "GET_REFILL_RATE_FACTOR": ["RR", r"OK(?P<refill_rate_factor>[0-4])"],  # Reads the pump refill rate factor (0=Full Out; 1=15:85; 2=30:70; 3=50:50; 4=70:30).
        "DISABLE_KEYPAD": ["KD"],  # Disables the keypad on the pump.
        "ENABLE_KEYPAD": ["KE"],  # Enables the keypad on the pump.
        "SET_PISTON_DIAMETER": ["SD"],  # Sets the piston diameter (0=.093, 1=.125, 2=.250).
        "GET_PISTON_DIAMETER": ["RD", r"OK(?P<piston_diameter_code>[0-2])"],  # Reads the piston diameter (0=.093, 1=.125, 2=.250).
        "SET_PUMP_STROKE": ["SS"],  # Sets the pump stroke (0=.125, 1=.250, 2=.500).
        "GET_PUMP_STROKE": ["RS", r"OK(?P<pump_stroke_code>[0-2])"],  # Reads the pump stroke (0=.125, 1=.250, 2=.500).
        "SET_PUMP_MATERIAL": ["SM"],  # Sets the pump material (0=ss, 1=pk).
        "GET_PUMP_MATERIAL": ["RM", r"OK(?P<pump_material_code>[01])"],  # Reads the pump material (0=ss, 1=pk).
        "GET_FAULT_STATUS": ["RX", r"OK(?P<motor_stall_code>[01])(?P<high_pressure_limit_code>[01])(?P<low_pressure_limit_code>[01])"],  # Reads motor stall, high pressure limit and low pressure limit codes (0=no fault, 1=fault).
        "SET_LED_AND_STOP": ["SX"],  # Sets the LED to red and stops pumping.
        "GET_ALL_PARAMETERS": ["RI", r"OK(?P<flowrate>\d{5})(?P<pressure>\d{4})(?P<high_pressure_limit>\d{4})(?P<low_pressure_limit>\d{4})(?P<compressibility_compensation>\d{2})(?P<refill_rate_factor>[0-4])(?P<piston_diameter_code>[0-2])(?P<pump_stroke_code>[0-2])(?P<pump_material_code>[01])(?P<keyboard_status>[01])(?P<fault_code>[0-3])(?P<run_status>[01])"],  # Reads pump flow rate, pressure, high pressure limit, low pressure limit, compressibility compensation, refill rate factor (0=full out, 1=15:85, 2=30:70, 3=50:50, 4=70:30), piston diameter (0=.093, 1=.125, 2=.250), piston stroke (0=.125, 1=.250, 2=.500), pump material (0=ss, 1=pk), keyboard status (0=enabled, 1=disabled), fault (0=none, 1=motor, 2=high pressure, 3=low pressure) and run status (0=pump not running, 1=pump running).
        "RESET_COMMAND_BUFFFER": ["Z"],  # Resets the command buffer.
    }

    def cmd_string(self, command_parameters: CommandParameterFactory) -> str:
        try:
            value = command_parameters.command_values["value"]
        except KeyError:
            value = ""
        return f"{command_parameters.commandstring}{value}"

    def initial_commands(self):
        self.stop_pumping()
        self.write("SET_REFILL_RATE_FACTOR", command_values={"value": "4"})

    def final_commands(self):
        self.stop_pumping()

    def handle_event(self, match: re.Match) -> None:
        raise NotImplementedError

    def dispense(self, rate, volume, **kwargs):
        if float(volume) == 0:
            return
        self.write("SET_VOL_RATE", command_values={"value": self._rateformat(rate)}, **kwargs)
        sleep(0.5)
        time_to_pump = 60 * float(volume) / float(rate)

        self.write("START", **kwargs).deferred_result

        def stop_pumping(result):
            self.stop_pumping(urgent=True)
            return result
        
        self.busy(TimeCondition("dispense finished", time_to_pump)).deferred_result.addBoth(stop_pumping)

    def dispense_with_compressability(self, compressability, rate, volume, **kwargs):
        if float(volume) == 0:
            return
        self.write("SET_COMPRESSIBILITY_COMPENSATION", command_values={"value": self._compressibilityformat(compressability)}, **kwargs)
        self.write("SET_VOL_RATE", command_values={"value": self._rateformat(rate)}, **kwargs)
        time_to_pump = 60 * float(volume) / float(rate)
        self.write("START", **kwargs).deferred_result
        def stop_pumping(result):
            self.stop_pumping(urgent=True)
            return result
        self.busy(TimeCondition("dispense finished", time_to_pump)).deferred_result.addBoth(stop_pumping)

    def continuous_flow(self, rate, **kwargs):
        self.write("SET_VOL_RATE", command_values={"value": self._rateformat(rate)}, **kwargs)
        self.write("START", **kwargs)

    def continuous_flow_with_compressability(self, compressability, rate, **kwargs):
        self.write("SET_COMPRESSIBILITY_COMPENSATION", command_values={"value": self._compressibilityformat(compressability)}, **kwargs)
        self.write("SET_VOL_RATE", command_values={"value": self._rateformat(rate)}, **kwargs)
        self.write("START", **kwargs)

    def stop_pumping(self, **kwargs):
        self.write("STOP", **kwargs)

    def set_refill_rate_factor(self, refillratefactor, **kwargs):
        self.write("SET_REFILL_RATE_FACTOR", command_values={"value": self._refillratefactorformat(refillratefactor)}, **kwargs)

    # def start_pumping(self, **kwargs):
    #     self.write("START", **kwargs)

    def compressability_compensation(self, compressability, **kwargs):
        self.write("SET_COMPRESSIBILITY_COMPENSATION", command_values={"value": self._compressibilityformat(compressability)}, **kwargs)

    @staticmethod
    def _rateformat(value):
        value = float(value)
        return f"{value:0>6.3f}"
    
    @staticmethod
    def _pressureformat(value):
        value = float(value)
        return f"{value:0>4.0f}"
    
    @staticmethod
    def _compressibilityformat(value):
        value = float(value)
        return f"{value:0>2.0f}"
    
    @staticmethod
    def _refillratefactorformat(value):
        value = float(value)
        return f"{value:0>2.0f}"
