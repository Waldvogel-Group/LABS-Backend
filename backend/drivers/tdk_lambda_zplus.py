from .psu_base import BaseDevice, CommandParameterFactory, parser, SinglechannelBaseDevice
from backend.conditions import ObservableGreaterOrEqualValueCondition
from backend.combined_observables import TimeIntegral

import re

from twisted.internet import defer


class Device(BaseDevice, SinglechannelBaseDevice):
    delimiter = "\r\n"
    command_parameter_factory = CommandParameterFactory(command_execution_time=.1)
    parser_parameter_factory = parser.ParserParameterFactory(parserclass=parser.SuccessParser)
    replies_commands = False
    log_name = "TDK Lambda Zplus"
    commands = {
        # manual: https://www.emea.lambda.tdk.com/de/KB/Zplus-User-Manual-low-voltage-models-10V-to-100V.pdf
        ### COMMON COMMANDS ###
        "CLEAR_STATUS": ["*CLS"],  # Clear Status command_name. Clears the entire status structure.
        "ENABLE_EVENT_STATUS": ["*ESE"],
        # Standard Event Status Enable command_name. Modifies the contents of the Event Status Enable Register.
        "GET_EVENT_STATUS": ["*ESE"],  # Standard Event Status query. Returns 3 digits code.
        "GET_EVENT_STATUS_REGISTER": ["*ESR"],
        # Standard Event Status Register query. Returns the contents of the Event Status Register.
        "GET_IDN": ["*IDN", r"(?P<manufacturer>.*),(?P<model_name>.*),(?P<serial_number>.*),(?P<firmware_version>.*)"],
        # Identification query. Returns an identification string in the following format: ‘Manufacturer, Model, Serial number, Firmware level’.
        "SET_OPERATION_COMPLETE": ["*OPC"],
        # Operation Complete command_name. Sets the Operation Complete bit in the Standard Event Status Register if all commands and queries are completed.
        "GET_OPERATION_COMPLETE": ["*OPC", r"(?P<operation_state>.*)"],
        # Operation Complete query. Returns ASCII ‘1’ as soon as all commands and queries are completed.
        "GET_OPTIONS": ["*OPT", r"(?P<options>.*)"],
        # The options (OPT) query returns a comma-separated list of all of the instrument options currently installed on the signal generator.
        "POWER_ON_STATUS_CLEAR": ["*PSC"],
        # The Power-On Status Clear (PSC) command_name controls the automatic power-on clearing of the Service Request Enable Register, the Standard Event Status Enable Register, and device-specific event enable registers. •• ON(1) - This choice enables the power-on clearing of the listed registers. •• OFF(0) - This choice disables the clearing of the listed registers and they retain their status when a power-on condition occurs.
        "GET_POWER_ON_STATUS_CLEAR": ["*PSC", r"(?P<status_clear>.*)"],  # Returns PSC Status
        "RESTORE_FROM_MEMORY": ["*RCL"],
        # Restores the power supply to a state previously stored in memory by *SAV command_name. Refer to Table 5-7.
        "RESET_TO_STATE": ["*RST"],
        # This command_name resets the power supply to a defined state as shown in Table 5-7. *RST also forces an ABORt command_name.
        "SAVE_CONFIG": ["*SAV"],  # The SAV command_name saves all applied configuration setting. Refer to Table 5-7.
        "ENABLE_SERVICE_REQUEST": ["*SRE"],
        # Service Request Enable command_name. Modifies the contents of the Service Request Enable Register.
        "GET_STATUS_SERVICE_REQUEST": ["*SRE", r"(?P<service_request>.*)"],  # Service Request query.
        "GET_STATUS_BYTE": ["*STB", r"(?P<status_byte>.*)"],
        # Status Byte query. Returns the contents of the Status Byte Register.
        "START_WAVEFORM": ["*TRG"],  # The Trigger command_name starts the waveform when the trigger source is set to BUS.
        "RESET_TRIGGER": ["ABOR"],
        # Resets the trigger system and places the power supply in an IDLE state without waiting for the completion of the trigger cycle.
        ### SUBSYSTEM COMMANDS ###
        # OUTPUT SUBSYSTEM
        "SET_OUTPUT": ["OUTP"],
        # This command_name enables or disables the power supply output. When output is turned off, voltage display shows ”OFF”.
        "GET_OUTPUT": ["OUTP", r"(?P<output_state>.*)"],  # Returns state 1 if Output is on and 0 if off
        "SET_POWER_ON": ["OUTP:PON"],
        # AUTO - The power supply output will return to its previous state when the latching fault condition is removed or to the stored state after AC recycle. SAFE - The power supply output will remain Off after the fault condition is removed or after AC recycle.
        "GET_POWER_ON": ["OUTP:PON", r"(?P<output_state>.*)"],
        "OUTPUT_PROTECTION_CLEAR": ["OUTP:PROT:CLE"],
        # This command_name clears the latch that disables the output when an over voltage (OVP), under voltage (UVP), or foldback (FOLD) fault condition is detected. All conditions that generate a fault must be removed before the latch can be cleared. The output is then restored to the state before the fault condition occurred.
        "SET_OUTPUT_PROTECTION_FOLDBACK": ["OUTP:PROT:FOLD"],
        # Foldback mode is used to disable the output when a transition is made between the operation modes. The power supply will turn off the output after a specified delay if the power supply makes transition into CV mode or into CC mode. This feature is particularly useful for protecting current or voltage sensitive loads.
        "OUTPUT_PROTECTION_DELAY": ["OUTP:PROT:DEL"],
        # Sets the delay time between the programming of an output change that produces a CV or CC status condition. This command_name applies to UVP and Foldback functions.
        "OUTPUT_ILC_MODE": ["OUTP:ILC:MODE"],
        # Selects the mode of operation of the Remote Inhibit protection. In OFF mode the power supply ignores J3-4 (ILC) status.
        "GET_OUTPUT_ILC_MODE": ["OUTP:ILC:MODE", r"(?P<mode>.*)"],
        # Returns the mode of operation of the Remote Inhibit protection.
        "OUTPUT_TTLTRG_MODE": ["OUTP:TTLT:MODE"],
        # Sets the operation of the Trigger Out signal to either OFF, Function Strobe or Trigger mode. Programming Mode NONE, FIX: •• In TRIG mode, trigger is generated when output status changes. •• In Function Strobe mode, an output pulse is generated automatically any time an output parameter such as output, voltage or current is programmed. Programming modes LIST or WAVE: •• In TRIG mode, trigger is generated when LIST or WAVE is completed. •• In Function Strobe mode, an output pulse is generated automatically any time a step is completed. The power supply Trigger Out signal is available at J3-3 connector on the rear panel.
        "GET_OUTPUT_TTLTRG_MODE": ["OUTP:TTLT:MODE"],  # Returns operation of Trigger Out signal
        "OUTPUT_RELAY1_STATE": ["OUTP:REL1:STAT"],
        # Sets pin J3-1 (1) state. The ON parameter is according to low level.
        "GET_OUTPUT_RELAY1_STATE": ["OUTP:REL1:STAT"],  # Returns pin J3-1 (1) state.
        "OUTPUT_RELAY2_STATE": ["OUTP:REL2:STAT"],
        # Sets pin J3-6 (2) state. The ON parameter is according to low level.
        "GET_OUTPUT_RELAY2_STATE": ["OUTP:REL2:STAT"],  # Returns pin J3-6 (2) state.
        "GET_OUTPUT_MODE": ["OUTP:MODE", r"(?P<mode>.*)"],
        # Returns the power supply operation mode. When the power supply is On (OUT 1) it will return ”CV” or ”CC”. When the power supply is OFF (OUT 0) it will return ”OFF”.
        # INSTRUMENT SUBSYSTEM
        "INSTRUMENT_COUPlE": ["INST:COUP"],
        "SET_INSTRUMENT_ADDRESS": ["INST:NSEL"],  # Select instrument address
        "GET_INSTRUMENT_ADDRESS": ["INST:NSEL", r"(?P<instrument_address>.*)"],  # Returns instrument address
        # VOLTAGE SUBSYSTEM
        "SET_VOLTAGE": ["VOLT"],
        # Sets the output voltage state in Volts. The range of voltage values are described in Table 7-5. The maximum number of characters is 12.
        "GET_VOLTAGE": ["VOLT", r"(?P<voltage_setpoint>\d+\.*\d*)"],
        # Sets the output voltage state in Volts. The range of voltage values are described in Table 7-5. The maximum number of characters is 12.
        "SET_VOLTAGE_MODE": ["VOLT:MODE"],
        # This command_name selects FIX, LIST, WAVE subsystems control over the power supply output voltage.
        "GET_VOLTAGE_MODE": ["VOLT:MODE", r"(?P<mode>.*)"],  # Returns voltage mode
        "SET_VOLTAGE_PROTECTION_LEVEL": ["VOLT:PROT:LEV"],
        # Sets the OVP level. The OVP setting range is given in Table 7-9. The number of characters after OVP is up to 12. The minimum setting level is approx. 105% of the set output voltage, or the state in Table 7-9, whichever is higher.
        "GET_VOLTAGE_PROTECTION_LEVEL": ["VOLT:PROT:LEV", r"(?P<level>.*)"],  # Returns OVP level.
        "SET_VOLTAGE_PROTECTION_LOW_STATE": ["VOLT:PROT:LOW:STAT"],
        # Sets the under voltage protection (UVP) status of the power supply. If the UVP status selected, then the under voltage protection is enabled.
        "GET_VOLTAGE_PROTECTION_LOW_STATE": ["VOLT:PROT:LOW:STAT", r"(?P<voltage_protection_state>.*)"],
        # Returns UVP status of power supply.
        "SET_VOLTAGE_PROTECTION_LOW": ["VOLT:PROT:LOW"],
        # Sets the under voltage protection (UVP) level of the power supply.
        "SET_VOLTAGE_TRIGGER": ["VOLT:TRIG"],
        # Programs the pending triggered voltage level of the power supply. The pending triggered voltage level is a stored state that is transferred to the output terminals when a trigger occurs.
        "GET_VOLTAGE_TRIGGER": ["VOLT:TRIG", r"(?P<trigger>.*)"],
        # returns the presently programmed voltage level. If the VOLT:TRIG level is not programmed, the default state is 0V.
        # CURRENT SUBSYSTEM
        "SET_CURRENT": ["CURR"],
        # Sets the output current state in Amperes. The range of current values are described in Tables 7-6, 7-7 and 7-8. The maximum number of characters is 12.
        "GET_CURRENT": ["CURR", r"(?P<current_setpoint>\d+\.*\d*)"],
        # returns the present programmed current level. CURR? MAX and CURR? MIN returns the maximum and minimum programmable current levels.
        "SET_CURRENT_MODE": ["CURR:MODE"],
        # This command_name selects FIX, LIST, WAVE subsystems control over the power supply output current.
        "GET_CURRENT_MODE": ["CURR:MODE", r"(?P<current_mode>.*)"],  # Returns the current mode
        "SET_CURRENT_TRIGGER": ["CURR:TRIG"],
        # Programs the pending triggered current level of the power supply. The pending triggered current level is a stored state that is transferred to the output terminals when a trigger occurs.
        "GET_CURRENT_TRIGGER": ["CURR:TRIG", r"(?P<current_trigger>.*)"],
        # returns the presently programmed triggered level. If no triggered level is programmed, the CURR level is returned.
        # MEASURE SUBSYSTEM
        "GET_MEASURE_CURRENT": ["MEAS:CURR", r"(?P<current>\d+\.*\d*)"],
        # Reads the measured output current. Returns a 5 digit string.
        "GET_MEASURE_VOLTAGE": ["MEAS:VOLT", r"(?P<voltage>\d+\.*\d*)"],
        # Reads the measured output voltage. Returns a 5 digit string.
        "GET_MEASURE_POWER": ["MEAS:POW", r"(?P<power>\d+\.*\d*)"],
        # Reads the measured output power. Returns a 5 digit string.
        # DISPLAY SUBSYSTEM
        "SET_DISPLAY_STATE": ["DISP:STAT"],  # Turns front panel voltage and Current display toggle On or Off.
        "GET_DISPLAY_STATE": ["DISP:STAT", r"(?P<display_state>.*)"],  # Returns state of display.
        "DISPLAY_FLASH": ["DISP:FLAS"],  # Makes front panel voltage and Current displays flash.
        # INITIATE SUBSYSTEM
        "INITIATE": ["INIT"],
        # Enables the trigger subsystem. If a trigger circuit is not enabled, all trigger commands are ignored.
        "INITIATE_CONTINUOUS": ["INIT:CONT"],
        # INIT:CONT 0 - Enables the trigger subsystem only for a single trigger action. The subsystem must be enabled prior to each subsequent trigger action. INIT:CONT 1 - Trigger system is continuously enabled and INIT is redundant.
        # LIST SUBSYSTEM
        "SET_LIST_COUNT": ["LIST:COUN"],
        # Sets the number of times that the list is executed before it is completed. The command_name accepts parameters in the range 1 through 9999, but any number greater than 9999 is interpreted as INFinity. Use INF if you wish to execute a list indefinitely.
        "GET_LIST_COUNT": ["LIST:COUN"],
        # Returns the number of times that the list is executed before it is completed.
        "SET_LIST_CURRENT": ["LIST:CURR"],
        # Specifies the output current points in a list. The current points are given in the command_name parameters, which are separated by commas.
        "GET_LIST_CURRENT": ["LIST:CURR"],  # Return the output current points in a list.
        "LIST_LOAD": ["LIST:LOAD"],
        # Loads from memory LIST type. Type voltage/current values, dwell values, STEP parameter and counter specified in stored numbers <1..4>
        "SET_LIST_DWELL": ["LIST:DWEL"],
        # Specifies the time interval that each state (point) of a list is to remain in effect.
        "GET_LIST_DWELL": ["LIST:DWEL"],
        # Returns the time interval that each state (point) of a list is to remain in effect.
        "SET_LIST_STEP": ["LIST:STEP"],
        # Determines if a trigger causes a list to advance only to its next point or to sequence through all the points. LIST:STEP AUTO - When triggered, it creates waveforms consecutively, until the list is completed. LIST:STEP ONCE - When triggered, it executes one step from the list.
        "GET_LIST_STEP": ["LIST:STEP"],  # Returns status of LIST:STEP
        "SET_LIST_VOLTAGE": ["LIST:VOLT"],
        # Specifies the output voltage points in a list. The voltage points are given in the command_name parameters, which are separated by commas.
        "GET_LIST_VOLTAGE": ["LIST:VOLT"],  # Returns comma-separated list of voltage points.
        "LIST_STORE": ["LIST:STOR"],
        # Saves data under specified numbers <1..4> of the last LIST typed (voltage or/and current, dwell time, STEP parameter and counter).
        # STATUS SUBSYSTEM
        "GET_STATUS_OPERATION_EVENT": ["STAT:OPER:EVEN"],
        # This query returns the state of the Event register. This is a read-only register that receives data from the Condition register according to Enable register setting. Reading the Event register clears it.
        "GET_STATUS_OPERATION_CONDITION": ["STAT:OPER:COND"],
        # Returns the state of the Condition register, which is a read-only register that holds the real-time (unlatched) operational status of the power supply.
        "SET_STATUS_OPERATION_ENABLE": ["STAT:OPER:ENAB"],
        # Sets the state of the Enable register. This register is a mask for enabling specific bits from the Condition register to the Event register.
        "GET_STATUS_OPERATION_ENABLE": ["STAT:OPER:ENAB"],
        # Returns the state of the Enable register. This register is a mask for enabling specific bits from the Condition register to the Event register.
        "GET_STATUS_QUESTIONABLE": ["STAT:QUES"],
        # This query returns the state of the Event register. It is a read-only register that receives data from the Condition register according to Enable register setting. Reading the Event register clears it.
        "GET_STATUS_QUESTIONABLE_CONDITION": ["STAT:QUES:COND"],
        # Returns the state of the Condition register, which is a read-only register that holds the real-time (unlatched) operational status of the power supply.
        "SET_STATUS_QUESTIONABLE_ENABLE": ["STAT:QUES:ENAB"],
        # Sets the state of the Enable register. This register is a mask for enabling specific bits from the Condition register to the Event register.
        "GET_STATUS_QUESTIONABLE_ENABLE": ["STAT:QUES:ENAB"],
        # Returns the state of the Enable register. This register is a mask for enabling specific bits from the Condition register to the Event register.
        # SYSTEM SUBSYSTEM
        "SET_SYSTEM_ERROR_ENABLE": ["SYST:ERR:ENAB"],  # Enables Error messages.
        "GET_SYSTEM_ERROR": ["SYST:ERR", r"(?P<err_no>.*),(?P<error>.*)"],
        # Returns the next error number and corresponding error message in the power supply error queue. Works as FIFO. When no error exists 0, ”No error” is returned.
        "SET_SYSTEM_LANGUAGE": ["SYST:LANG"],  # Sets system language to either GEN or SCPI
        "GET_SYSTEM_LANGUAGE": ["SYST:LANG", r"(?P<language>.*)"],  # Returns system language (either GEN or SCPI)
        "SET_SYSTEM_REMOTE": ["SYST:REM"],  # Sets the power supply to local or remote mode.
        "GET_SYSTEM_REMOTE": ["SYST:REM", r"(?P<remote_setting>.*)"],  # Returns mode of power supply
        "GET_SYSTEM_VERSION": ["SYST:VERS", r"Rev:(?P<revision>.*)"],  # Returns system version
        "GET_SYSTEM_DATE": ["SYST:DATE", r"(?P<year>.*)/(?P<month>.*)/(?P<day>.*)"],  # Returns system date
        "GET_SYSTEM_PON_TIME": ["SYST:PON:TIME", r"(?P<time>.*)"],  # Time measured from first power On.
        # TRIGGER SUBSYSTEM
        "SET_TRIGGER": ["TRIG"],
        # When the Trigger subsystem is enabled, TRIG generates an immediate trigger signal that bypasses selected TRIG:DEL.
        "SET_TRIGGER_DELAY": ["TRIG:DEL"],
        # Sets the time delay between the detection of an event on the specified trigger source and the start of any corresponding trigger action on the power supply output.
        "GET_TRIGGER_DELAY": ["TRIG:DEL"],
        # Returns the time delay between the detection of an event on the specified trigger source and the start of any corresponding trigger action on the power supply output.
        "SET_TRIGGER_SOURCE": ["TRIG:SOUR"],
        # Selects the power supply input trigger source as follows: BUS (*TRG & TRIG) and Front Panel EXT Mainframe backplane Trigger IN PIN
        "GET_TRIGGER_SOURCE": ["TRIG:SOUR"],  # Returns the power supply input trigger source
        # WAVE SUBSYSTEM
        "SET_WAVE_COUNT": ["WAVE:COUN"],
        # Sets the number of times that the list is executed before it is completed. The command_name accepts parameters in the range 1 through 9999. Any number greater than 9999 is interpreted as INFinity.Use INF if you wish to execute a list indefinitely.
        "GET_WAVE_COUNT": ["WAVE:COUN"],
        # Returns the number of times that the list is executed before it is completed.
        "SET_WAVE_CURRENT": ["WAVE:CURR"],
        # This command_name specifies the output current points in a waveform list. The current points are given in the command_name parameters, which are separated by commas.
        "GET_WAVE_CURRENT": ["WAVE:CURR"],  # Returns the output current points in a waveform list.
        "SET_WAVE_LOAD": ["WAVE:LOAD"],
        # Loads Voltage or Current, Time, STEP parameter and counter values to a specific location in the memory defined by numbers <1..4>.
        "SET_WAVE_STEP": ["WAVE:STEP"],
        # WAVE:STEP AUTO - When triggered, creates waveforms consecutively, until the wave is completed. WAVE:STEP ONCE - When triggered, it executes one step from the list.
        "GET_WAVE_STEP": ["WAVE:STEP"],  # Returns status of WAVE:STEP
        "SET_WAVE_STORE": ["WAVE:STORE"],
        # Stores Voltage or Current, Time, STEP parameter and counter values to specific location in the memory defined by numbers <1..4>.
        "SET_WAVE_TIME": ["WAVE:TIME"],  # Sets the slope time of the waveform.
        "GET_WAVE_TIME": ["WAVE:TIME"],  # Returns the slope time of the waveform.
        "SET_WAVE_VOLTAGE": ["WAVE:VOLT"],  # Specifies the output voltage points in a waveform list.
        "GET_WAVE_VOLTAGE": ["WAVE:VOLT"],  # Returns the output voltage points in a waveform list.
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aoc = None
        self._current_measuring = None
        self._voltage_measuring = None

    def initial_commands(self):
        super().write("SET_INSTRUMENT_ADDRESS", command_values={"value": 1})
        super().write("CLEAR_STATUS")
        super().write("SET_SYSTEM_ERROR_ENABLE")
        self.stop_current()
        super().initial_commands()

    def final_commands(self):
        self.stop_current()

    def handle_event(self, match: re.Match) -> None:
        pass

    def cmd_string(self, command_parameters: CommandParameterFactory) -> str:
        query = sep = ""
        option = ""
        value = ""
        if command_parameters.query:
            query = "?"
        if "option" in command_parameters.command_values.keys():
            sep = ":"
            option = command_parameters.command_values["option"]
        if "value" in command_parameters.command_values.keys():
            value = " " + str(command_parameters.command_values["value"])
        message = f"{command_parameters.commandstring}{value}{sep}{option}{query}"
        return message

    def _start_aoc(self):
        self._stop_aoc()
        self._aoc = TimeIntegral(self, "amount_of_charge", "current")
        self._aoc.start()

    def _stop_aoc(self):
        try:
            self._aoc.stop()
        except AttributeError:
            pass

    def start_measuring_output(self, interval = .5, condition = None):
        def start_aoc(result):
            self._start_aoc()
            return result

        self._current_measuring = self.repeated_query("GET_MEASURE_CURRENT", interval, condition, inter_command_time=.001)
        self._voltage_measuring = self.repeated_query("GET_MEASURE_VOLTAGE", interval, condition, inter_command_time=.001)
        self._current_measuring.deferred_result.addCallback(start_aoc)

    def _stop_measuring_output(self):
        self._stop_aoc()
        try:
            self._current_measuring.stop_running()
            self._voltage_measuring.stop_running()
        except AttributeError:
            pass
        else:
            self._current_measuring = None
            self._voltage_measuring = None

    def output_constant_current(self, current, max_voltage="MAX", amount_of_charge=None):
        self.write("SET_CURRENT", command_values={"value": current})
        self.write("SET_VOLTAGE", command_values={"value": max_voltage})

        deferred_result = self.write("SET_OUTPUT", command_values={"value": 1}).deferred_result
        
        if amount_of_charge:
            def get_time_passed(results):
                try:
                    old_time = results[1][1].time
                    new_time = results[0][1].time
                except AttributeError:
                    self.log.error(f"Constant current output failed with: {results}")
                    for (success, result) in results:
                        if not success:
                            raise result
                else:
                    time_passed = results[1][1].time - results[0][1].time
                    self.log.info(f"Amount of charge reached after {time_passed} s.")
                    return results
                
            condition = ObservableGreaterOrEqualValueCondition("amount of charge reached", self, "amount_of_charge", str(amount_of_charge))
            defer.DeferredList([deferred_result, self.busy(condition).deferred_result]).addCallback(get_time_passed)
            self.start_measuring_output()
            self.stop_current()     
        else:
            self.start_measuring_output()

        return deferred_result

    def output_constant_voltage(self, voltage, max_current="MAX", amount_of_charge=None):
        return self.output_constant_current(max_current, voltage, amount_of_charge)

    def stop_current(self):
        def stop_measuring(result):
            self._stop_measuring_output()
            return result
        cmd = self.write("SET_OUTPUT", command_values={"value": 0})
        cmd.deferred_execution.addCallback(stop_measuring)
        return cmd

    def query(self, command_name: str, **kwargs):
        return super().write(command_name, query=True, **kwargs)

    def write(self, command_name: str, **kwargs):
        with self.commandseries as series:
            cmd = super().write(command_name, **kwargs)
            try:
                kwargs.pop("command_values")
            except KeyError:
                pass
            self.query("GET_OPERATION_COMPLETE", retries=0, parser_kwargs={"expected_values": {"operation_state": "1"}}, **kwargs)
        return cmd
