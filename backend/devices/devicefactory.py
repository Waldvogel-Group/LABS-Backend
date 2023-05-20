import importlib

from twisted.logger import Logger
from twisted.internet import defer

from .helpers_exceptions import UnknownDeviceError, UnknownChannelError, AddressInUseError


class DeviceFactory:
    def __init__(self):
        self.log = Logger()
        self.deferred_devices: dict[str: defer.Deferred] = {}

    def construct_device(self, driver: str, address: str, channel: int = None, **kwargs) -> defer.Deferred:
        try:
            device_module = importlib.import_module(f"backend.drivers.{driver}")
            deferred_device = self.deferred_devices[address]
        except ModuleNotFoundError as e:
            self.log.error("Error while trying to import {devicename}! {error}", devicename=driver, error=e)
            return defer.fail(UnknownDeviceError())
        except KeyError:
            device = device_module.Device(address, **kwargs)
            deferred_protocol = device.connect()
            deferred_device = self.deferred_devices[address] = defer.Deferred()

            def callback_device(protocol, connected_device):
                deferred_device.callback(connected_device)
                return protocol

            def remove_device(reason):
                self.deferred_devices.pop(address)
                return reason

            deferred_protocol.addCallbacks(callback_device, remove_device, [device])
        else:
            checked_device = defer.Deferred()

            def check_device(device):
                if not isinstance(device, device_module.Device):
                    checked_device.errback(AddressInUseError())
                else:
                    checked_device.callback(device)
                return device
            deferred_device.addCallback(check_device)
            deferred_device, _ = checked_device, deferred_device

        if channel is None:
            return deferred_device
        else:
            deferred_channel = defer.Deferred()

            def callback_channel(connected_device, channelnumber):
                try:
                    channel_proxy = connected_device.channels[channelnumber]
                except KeyError:
                    self.log.error("Channel {channelnumber} does not exist on {device} with address {address}",
                                   channelnumber=channelnumber, device=deferred_device.result, address=address)
                    return defer.fail(UnknownChannelError())
                else:
                    deferred_channel.callback(channel_proxy)
                finally:
                    return connected_device
            deferred_device.addCallback(callback_channel, channel)
            return deferred_channel
