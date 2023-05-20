from .multipos_valve_base import BaseDevice, SinglechannelBaseDevice, commandstate, CommandParameterFactory
import re


class Device(SinglechannelBaseDevice, BaseDevice):
    reply_to_state = {"OK": commandstate.Success}
    error_patterns = [r"ERROR:(?P<code>.*),(?P<message>.*)"]
    replies_commands = True
    log_name = "Knauer AzuraVU"

    command_parameter_factory = CommandParameterFactory(inter_command_time=1)

    commands = {
        # manual: TODO: available somewhere?
        ### COMMON COMMANDS ###
        "GET_IDN": ["IDENTIFY",
                    r"IDENTIFY:(?P<device_type>.*),(?P<manufacturer>.*),(?P<model_name>.*),(?P<serial_number>.*),(?P<firmware_version>.*),(?P<position_count>.*),(?P<ports_number>.*)"],
        "SET_POS": ["POSITION"],
        "GET_POS": ["POSITION", r"POSITION:(?P<position>.*)"],
        "GET_STATUS": ["STATUS", r"STATUS:(?P<system_tick_count>.*),(?P<instrument_state>.*),(?P<current_error_code>.*),(?P<last_warning_code>.*),(?P<current_position>.*),(?P<run_time_ms>.*),(?P<home_in_state>.*),(?P<backward_in_state>.*),(?P<forward_in_state>.*),(?P<start_in_state>.*),(?P<event_out_state>.*),(?P<encoder_position>.*),(?P<encoder_angle>.*),(?P<valve_shaft_position>.*),(?P<last_reposition_diagnostic>.*),(?P<interface_state>.*),(?P<CPU_temperature>.*)"],
        "GET_VALVE": ["VALVE", r"VALVE:(?P<serial_number>[0-9A-Za-z]*),(?P<valve_type>-?[0-9]*),(?P<position_count>[0-9]*),(?P<port_count>[0-9]*),(?P<home_angle>[0-9]*),(?P<maximum_pressure>[0-9]*),(?P<velocity_factor>[0-9]*),(?P<maximum_seal_cycles>[0-9]*),(?P<switch_cycle_amount>[0-9]*),(?P<global_scaler_override>[0-9]*),(?P<torque_range>[0-9]*),(?P<reserved_4>[0-9]*),(?P<part_number>[^,]*),(?P<position_info>.*)"],
    }

    def cmd_string(self, command_parameters: CommandParameterFactory) -> str:
        if command_parameters.query:
            query = "?"
        else:
            query = ""
        try:
            value = command_parameters.command_values["value"]
        except KeyError:
            sep = ""
            value = ""
        else:
            sep = ":"
        value = str(value)
        command = command_parameters.commandstring
        return f"{command}{sep}{value}{query}"

    def set_position(self, position, **kwargs):
        with self.commandseries as series:
            result = self.write("SET_POS", command_values={"value": int(float(position))}, **kwargs)
            self.query("GET_POS")
        return result

    def initial_commands(self):
        self.query("GET_IDN", inter_command_time=0)
        self.set_position(1)
        super().initial_commands()

    def final_commands(self):
        self.set_position(1)

    def handle_event(self, match: re.Match) -> None:
        pass

    def _get_valve_positions(self):
        return self.query("GET_VALVE", inter_command_time=0)

    def _move_position(self, result, step):
        pos = int(result.parameters["position"]) + step
        if pos > self.positions:
            pos -= self.positions
        elif pos < 1:
            pos += self.positions
        self.set_position(pos, urgent=True)

    def next_position(self):
        return self.query("GET_POS").deferred_result.addCallback(self._move_position, +1)

    def previous_position(self):
        return self.query("GET_POS").deferred_result.addCallback(self._move_position, -1)
