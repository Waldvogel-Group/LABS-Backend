#This wants to be the driver for a Magritek Spinsolve 60 benchtop NMR
import re
from backend.conditions.conditions import TimeCondition, ObservableEqualsValueCondition
from backend.commands.parser import ParserParameterFactory, SuccessParser
from .nmr_base import BaseDevice, SinglechannelBaseDevice, commandstate, CommandParameterFactory
from backend.devices.base import AbstractBaseDevice
import socket
import time


class Device(BaseDevice, SinglechannelBaseDevice):

    #is_true = AbstractBaseDevice._was_event(reply=True)
    log_name = "BenchtopNMR"
    replies_commands = False
    reply_to_state = {"<?xml": commandstate.Success} #r"secondsRemaining=\"(?P<secondsRemaining>.*)\"""r"<.+>"
    delimiter = "</Message>"  #"\r\n"receiving_delimiter = "</Message>"
    #sending_delimiter = ""
    event_patterns = [
        r"completed=\"(?P<completed>.+?)\"",
        # r"secondsRemaining=\"(?P<secondsRemaining>[0-9]+)",
        # r"(?P<completed>.+)",
        r"percentage",
        r"status=\"Ready\"",
        r"error=\"\""
        # r"[\d\D]+"
    ]
#    error_pattern = [
#        r"error=\".+?\""
#    ]
    command_parameter_factory = CommandParameterFactory(timeout=5.0, inter_command_time=0.5, retries=3)
    parser_parameter_factory = ParserParameterFactory(parserclass=SuccessParser)

    commands = {
        # Asks for protocol options
        "PROTOCOL_OPTIONS" : ["<Message><AvailableOptionsRequest protocol='1D PROTON'/></Message>"],
        # Start a CheckShim
        "CHECKSHIM" : ["<Message><CheckShimRequest/></Message>",r"(?P<Text>.+)"],#status=\"(?P<Status>.+?)\".+"],#r".+"],# r"OK(?P<refill_rate_factor>[0-4])"]
        "WaitCommand" : ["",r".*"],
        # Aborts current action
        "ABORT" : ["<Message><Abort/></Message>"],
        # Starts a Proton Quickscan
        "QUICKSCAN" : ["<Message><Start protocol='1D PROTON'><Option name='Scan' value='QuickScan'/></Start></Message>"],
    }
#(?m)
# <?xml version="1.0" encoding="utf-8"?>
#   <Message>
#       <StatusNotification timestamp="09:37:49">
#            <State protocol="SHIM" status="Running" dataFolder="" />
#       </StatusNotification>
#   </Message>
    def cmd_string(self, command_parameters: CommandParameterFactory) -> str:
        try:
            value = command_parameters.command_values["value"]
        except KeyError:
            value = ""
        return f"{command_parameters.commandstring}{value}"

    def stop_measurement(self, **kwargs):
        print("NMR function Stop_measurment")
        #self.write("ABORT")

    def nmr_wait_function(self):
        HOST = "127.0.0.1"    # Replace
        PORT = 13000          # Default port
        print('Connect to ' + HOST + ':' + str(PORT))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((HOST, PORT))
        s.send("<Message><Start protocol='1D PROTON'><Option name='Scan' value='StandardScan'/></Start></Message>".encode())
        self.busy(TimeCondition("waiting finished in", 70))

    def start_shimming(self):
        # problem withe the second measuremnt while using the self.write command
        # TODO fix this
        HOST = "127.0.0.1"    # Replace
        PORT = 13000          # Default port
        print('Connect to ' + HOST + ':' + str(PORT))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((HOST, PORT))
        s.send("<Message><CheckShimRequest/></Message>".encode())
        self.busy(TimeCondition("shimming finished in", 18))

    def shim_on_solvent(self):
        HOST = "127.0.0.1"    # Replace
        PORT = 13000          # Default port
        print('Connect to ' + HOST + ':' + str(PORT))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((HOST, PORT))
        s.send("<Message><Start protocol='SHIM 1H SAMPLE'><Option name='Mode' value='Manual' /><Option name='manualStart' value='60' /><Option name='manualEnd' value='-40' /><Option name='Shim' value='QuickShim2' /></Start></Message>".encode())
        self.busy(TimeCondition("shimming finished in", 310))

    def powershim_on_solvent(self):
        HOST = "127.0.0.1"    # Replace
        PORT = 13000          # Default port
        print('Connect to ' + HOST + ':' + str(PORT))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((HOST, PORT))
        s.send("<Message><Start protocol='SHIM 1H SAMPLE'><Option name='Mode' value='Manual' /><Option name='manualStart' value='60' /><Option name='manualEnd' value='-40' /><Option name='Shim' value='PowerShim' /></Start></Message>".encode())
        self.busy(TimeCondition("shimming finished in", 2500))


    def h1_measurement(self):
        HOST = "127.0.0.1"    # Replace
        PORT = 13000          # Default port
        print('Connect to ' + HOST + ':' + str(PORT))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((HOST, PORT))
        s.send("<Message><Start protocol='1D PROTON'><Option name='Scan' value='QuickScan'/></Start></Message>".encode())
        self.busy(TimeCondition("measurement finished in", 18))

    def f19hdec_measurement(self):
        HOST = "127.0.0.1"    # Replace
        PORT = 13000          # Default port
        print('Connect to ' + HOST + ':' + str(PORT))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((HOST, PORT))
        s.send("<Message><Start protocol='1D FLUORINE HDEC WALTZ'><Option name='Number' value='128'/><Option name='AcquisitionTime' value='3.2'/><Option name='RepetitionTime' value='30'/><Option name='PulseAngle' value='90'/><Option name='centerFrequency' value='-110'/><Option name='decouple' value='On'/><Processing><Press Name='MNOVA'/></Processing></Start></Message>".encode())
        self.busy(TimeCondition("measurement finished in", 3900))

    def start_measurement(self, **kwargs):
        pass

    def initial_commands(self):
        pass

    def final_commands(self):
        pass

    # def cmd_string(self, command_parameters: CommandParameterFactory) -> str:
    #     return command_parameters.commandstring
    
    def handle_event(self, match: re.Match) -> None:
        pass

    #def start_shimming(self):
        # problem withe the second measuremnt while using the self.write command
        # TODO fix this
        ##HOST = "127.0.0.1"    # Replace
        ##PORT = 13000          # Default port
        ##print('Connect to ' + HOST + ':' + str(PORT))
        ##s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ##s.connect((HOST, PORT))
        ##s.send("<Message><CheckShimRequest/></Message>".encode())
        # def check_chunk(s : socket):
        #     s.settimeout(5.0)
        #     chunk = s.recv(8192)
        #     if re.search(chunk,r"Please run a quickshim"):
        #         s.send("<Message><QuickShimRequest/></Message>".encode())
        #     else:
        #         print("No QuickShim needed!")
        #     print(chunk) #TODO delete me plx!
        # def stop_measurement(result):
        #     self.stop_measurement(urgent=True)
        #     return result
        ##self.busy(TimeCondition("shimming finished in", 18))
        #print("Hallo Welt!")
        #check_chunk(s)
        #.deferred_result.addBoth(stop_measurement)
        #observable = self
        #self.busy(ObservableEqualsValueCondition("shimming finished",self,"completed","true")).deferred_result.addBoth(stop_measurement)
