from twisted.internet import defer

from backend import conditions
from .thermostat_base import BaseDevice, CommandParameterFactory, parser, SinglechannelBaseDevice
import re


class Device(SinglechannelBaseDevice, BaseDevice):
    delimiter = "\r\n"
    serial_parameters = {"baudrate": 4800, "parity": "E", "rtscts": 1, "bytesize": 7}
    replies_commands = False
    parser_parameter_factory = parser.ParserParameterFactory(parserclass=parser.SuccessParser)
    error_patterns = [r"(?P<error_code>-\d{2}) (?P<error>[ +\w+]+)"]
    log_name = "Presto A40"
    commands = {
        # in commands
        "GET_VERSION": ["version", r"(?P<devicename>.*) VERSION (?P<version>[\d\.]*)"],
        "GET_STATUS": ["status", r"(?P<status_code>\d{2}) (?P<status>.+)"],
        "GET_BATH_TEMP": ["in_pv_00", r"(?P<current_temperature>[\d\.]*)"],
        "GET_CURRENT_POWER": ["in_pv_01", r"(?P<current_power>[\d\.]*)"],
        "GET_EXT_PROBE_TEMP": ["in_pv_02", r"(?P<temperature_setpoint1>[-\d\.]*)"],
        "GET_SAFETY_TEMP_TANK": ["in_pv_03", r"(?P<safety_tank_temperature>[\d\.]*)"],
        "GET_OVERTEMP_SAFETY": ["in_pv_04", r"(?P<overtemperature_safety>[\d\.]*)"],
        "GET_INT_PRESSURE": ["in_pv_05", r"(?P<internal_pressure>[\d\.]*)"],
        "GET_EXT_PRESSURE": ["in_pv_06", r"(?P<external_pressure>[-\d\.]*)"],
        "GET_EXT_RATE": ["in_pv_07", r"(?P<external_rate>[-\d\.]*)"],
        # "GET_PRESSURE_2": ["in_pv_08", r"(?P<pressure2>[\d\.]*)"],
        # "GET_RATE_COOLING_WATER": ["in_pv_09", r"(?P<rate_cooling_water>[\d\.]*)"],
        "GET_EXT_PROBE_TEMP_2": ["in_pv_12", r"(?P<external_probe_temperature>[-\d\.]*)"],
        "GET_EXT_TEMP": ["in_pv_15", r"(?P<external_temperature>[-\d\.]*)"],
        
        "GET_WORKING_TEMP_1": ["in_sp_00", r"(?P<temperature_setpoint1>[-\d\.]*)"],
        "GET_WORKING_TEMP_2": ["in_sp_01", r"(?P<temperature_setpoint2>[-\d\.]*)"],
        "GET_WORKING_TEMP_3": ["in_sp_02", r"(?P<temperature_setpoint3>[-\d\.]*)"],
        "GET_OVERTEMP": ["in_sp_03", r"(?P<overtemperature>[\d\.]*)"],
        "GET_UNDERTEMP": ["in_sp_04", r"(?P<undertemperature>[-\d\.]*)"],
        "GET_TEMP_SET_EXT_PROGRAM": ["in_sp_05", r"(?P<temperature_setpoint_external_program>[-\d\.]*)"],
        "GET_WATCHDOG_SETTING": ["in_sp_06", r"(?P<watchdog_setpoint>[\d\.]*)"],
        "GET_PUMP_SETTING": ["in_sp_07", r"(?P<pump_setpoint>[1-4])"],
        "GET_RATE_SETTING": ["in_sp_08", r"(?P<rate_setpoint>[\d\.]*)"],
        "GET_PUMP_PRESSURE_SETTING": ["in_sp_09", r"(?P<pressure_setpoint>[\d\.]*)"],
        "GET_SELECTED_VAR_SETTING": ["in_sp_10", r"(?P<selected_var_setting>[-\d\.]*)"],
        "GET_TEMPERATURE_INDICATION": ["in_sp_11", r"(?P<temperature_indication>[-\d\.]*)"],
        "GET_PRESSURE_INDICATION": ["in_sp_12", r"(?P<pressure_indication>[\d\.]*)"],
        "GET_FLOW_INDICATION": ["in_sp_13", r"(?P<flow_indication>[\d\.]*)"],
        "GET_OVERPRESS": ["in_sp_14", r"(?P<overpressure>[\d\.]*)"],
        "GET_UNDERPRESS": ["in_sp_15", r"(?P<underpressure>[\d\.]*)"],
        "GET_PRESSURE_LIMIT_5S": ["in_sp_16", r"(?P<pressure_limit_5s>[\d\.]*)"],
        "GET_PRESSURE_LIMIT_1S": ["in_sp_17", r"(?P<pressure_limit_1s>[\d\.]*)"],
        "GET_OVERFLOW": ["in_sp_18", r"(?P<overflow>[\d\.]*)"],
        "GET_UNDERFLOW": ["in_sp_19", r"(?P<underflow>[\d\.]*)"],
        "GET_MAX_TEMP_GRAD_HEATING": ["in_sp_25", r"(?P<max_temperature_gradient_heating>[-\d\.]*)"],
        "GET_MAX_TEMP_GRAD_COOLING": ["in_sp_26", r"(?P<max_temperature_gradient_cooling>[-\d\.]*)"],
        "GET_MAX_COOLING_POWER": ["in_hil_00", r"(?P<max_cooling_power>[-\d\.]*)"],
        "GET_MAX_HEATING_POWER": ["in_hil_01", r"(?P<max_heating_power>[\d\.]*)"],
        "GET_SETPOINT": ["in_mode_01", r"(?P<setpoint>[0-2])"],
        "GET_SELFTUNING": ["in_mode_02", r"(?P<selftuning>[0-2])"],
        "GET_TYPE_EXT_PROGRAM": ["in_mode_03", r"(?P<external_programm_type>[-0-1])"],
        "GET_TEMP_CONTROL": ["in_mode_04", r"(?P<temperature_control>[0-1])"],
        "GET_UNIT_IN_STOP_START_STATE": ["in_mode_05", r"(?P<stop_start_state>[0-1])"],
        "GET_ADJUSTED_CONTROL_DYNAMICS": ["in_mode_08", r"(?P<control_dynamics>[0-1])"],
        "GET_PUMP_CONTROL": ["in_mode_09", r"(?P<pump_control>[0-3])"],
        "GET_PUMP_CONTROL": ["in_mode_12", r"(?P<pump_control>[0-4])"],
        "GET_DIFF_WORKING_SAFETY_SENSOR": ["in_par_00", r"(?P<difference_working_safety_sensor>[\d\.]*)"],
        "GET_TE": ["in_par_01", r"(?P<te>[\d\.]*)"],
        "GET_SI": ["in_par_02", r"(?P<si>[\d\.]*)"],
        "GET_TI": ["in_par_03", r"(?P<ti>[\d\.]*)"],
        "GET_COSPEED_EXT": ["in_par_04", r"(?P<cospeed_external>[\d\.]*)"],
        "GET_XP_INT": ["in_par_06", r"(?P<xp_internal>[\d\.]*)"],
        "GET_TN_INT": ["in_par_07", r"(?P<tn_internal>[\d\.]*)"],
        "GET_TV_INT": ["in_par_08", r"(?P<tv_internal>[\d\.]*)"],
        "GET_XP_CASC_CONTROLLER": ["in_par_09", r"(?P<xp_cascade_controller>[\d\.]*)"],
        "GET_PROP_SHARE_CASC_CONTROLLER": ["in_par_10", r"(?P<proportional_share_cascade_controller>[\d\.]*)"],
        "GET_TN_CASC_CONTROLLER": ["in_par_11", r"(?P<tn_cascade_controller>[\d\.]*)"],
        "GET_TV_CASC_CONTROLLER": ["in_par_12", r"(?P<tv_cascade_controller>[\d\.]*)"],
        "GET_ADJ_MAX_TEMP_CASC_CONTROLLER": ["in_par_13", r"(?P<max_temperature_cascade_controller>[\d\.]*)"],
        "GET_ADJ_MIN_TEMP_CASC_CONTROLLER": ["in_par_14", r"(?P<min_temperature_cascade_controller>[-\d\.]*)"],
        "GET_UPPER_BAND_LIMIT": ["in_par_15", r"(?P<upper_band_limit>[\d\.]*)"],
        "GET_LOWER_BAND_LIMIT": ["in_par_16", r"(?P<lower_band_limit>[\d\.]*)"],
        # out commands
        "SET_USE_WORKING_TEMP": ["out_mode_01"],
        "SET_SELFTUNING": ["out_mode_02"],
        "SET_EXT_PROGRAM_MODE": ["out_mode_03"],
        "SET_TEMP_CONTROL_INT_EXT": ["out_mode_04"],
        "SET_START_STOP": ["out_mode_05"],
        "SET_CONTROL_DYNAMICS": ["out_mode_08"],
        "SET_PUMP_CONTROL": ["out_mode_09"],
        "SET_WORKING_TEMP_1": ["out_sp_00"],
        "SET_WORKING_TEMP_2": ["out_sp_01"],
        "SET_WORKING_TEMP_3": ["out_sp_02"],
        "SET_OVERTEMP": ["out_sp_03"],
        "SET_UNDERTEMP": ["out_sp_04"],
        "SET_WATCHDOG": ["out_sp_06"],
        "SET_PUMP_PRESSURE_STAGE": ["out_sp_07"],
        "SET_FLOWRATE": ["out_sp_08"],
        "SET_PRESSURE": ["out_sp_09"],
        "SET_VAR_SERIAL_INTERFACE": ["out_sp_10"],
        "SET_TEMP_UNIT": ["out_sp_11"],
        "SET_PRESS_UNIT": ["out_sp_12"],
        "SET_FLOWRATE_UNIT": ["out_sp_13"],
        "SET_OVERPRESS": ["out_sp_14"],
        "SET_UNDERPRESS": ["out_sp_15"],
        "SET_PRESSURE_LIMIT_5S": ["out_sp_16"],
        "SET_PRESSURE_LIMIT_1S": ["out_sp_17"],
        "SET_OVERFLOW": ["out_sp_18"],
        "SET_UNDERFLOW": ["out_sp_19"],
        "SET_MAX_TEMP_GRAD_HEATING": ["out_sp_25"],
        "SET_MIN_TEMP_GRAD_HEATING": ["out_sp_26"],
        "SET_MAX_COOLING_POWER": ["out_hil_00"],
        "SET_MAX_HEATING_POWER": ["out_hil_01"],
        "SET_COSPEED_EXT": ["out_par_04"],
        "SET_XP_INT": ["out_par_06"],
        "SET_TN_INT": ["out_par_07"],
        "SET_TV_INT": ["out_par_08"],
        "SET_XP_CASC_CONTROLLER": ["out_par_09"],
        "SET_PROP_SHARE_CASC_CONTROLLER": ["out_par_10"],
        "SET_TN_CASC_CONTROLLER": ["out_par_11"],
        "SET_TV_CASC_CONTROLLER": ["out_par_12"],
        "SET_ADJ_MAX_TEMP_CASC_CONTROLLER": ["out_par_13"],
        "SET_ADJ_MIN_TEMP_CASC_CONTROLLER": ["out_par_14"],
        "SET_UPPER_BAND_LIMIT": ["out_par_15"],
        "SET_LOWER_BAND_LIMIT": ["out_par_16"],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._measuring_temperature = None

    def cmd_string(self, command_parameters: CommandParameterFactory) -> str:
        command = command_parameters.commandstring
        try:
            value = f" {command_parameters.command_values['value']}"
        except KeyError:
            value = ""
        return f"{command}{value}"

    def final_commands(self):
        self.stop_tempering()

    def get_current_temperature(self, **kwargs):
        self.query("GET_BATH_TEMP", **kwargs)

    def start_measuring_temperature(self, interval = 1, condition = None):
        self._measuring_temperature = self.repeated_query("GET_BATH_TEMP", interval, condition, inter_command_time=.001)

    def _stop_measuring_temperature(self):
        try:
            self._measuring_temperature.stop_running()
        except AttributeError:
            pass
        else:
            self._measuring_temperature = None

    def handle_event(self, match: re.Match) -> None:
        raise NotImplementedError("Device doesn't support eventstrings!")

    def initial_commands(self):
        self.write("SET_START_STOP", command_values={"value": "0"})

    def set_temperature(self, temperature, tolerance, tolerance_duration, **kwargs):
        lower_limit, upper_limit = float(temperature) - float(tolerance), float(temperature) + float(tolerance)
        with self.commandseries as series:
            series.parameters.urgent = True
            self.write("SET_USE_WORKING_TEMP", command_values={"value": "0"}, **kwargs)
            self.write("SET_WORKING_TEMP_1", command_values={"value": f"{float(temperature):.2f}"}, **kwargs)
            self.write("SET_START_STOP", command_values={"value": "1"}, **kwargs)
            condition = conditions.OngoingCondition("temperature held", tolerance_duration, 
                                                    conditions.ObservableInsideIntervalCondition(
                "temperature reached", self, "current_temperature", lower_limit, upper_limit
                )
            )
        self.busy(condition, urgent=True)
        self.start_measuring_temperature()

    def stop_tempering(self, **kwargs):
        def stop_measuring(result):
            self._stop_measuring_temperature()
            return result
        self.write("SET_START_STOP", command_values={"value": "0"}, **kwargs).deferred_result.addCallback(stop_measuring)
        
    def query(self, command_name: str, **kwargs):
        return super().write(command_name, query=True, **kwargs)

    def write(self, command_name: str, **kwargs):
        with self.commandseries as series:
            cmd = super().write(command_name, **kwargs)
            try:
                kwargs.pop("command_values")
            except KeyError:
                pass
            self.query("GET_STATUS", retries=0, **kwargs)
        return cmd
