class UnknownConnectionTypeError(Exception):
    """Raised when an address is not of any known format"""
    pass


class DeviceShutdownError(Exception):
    """Raised when a method of a device in Shutdown state is called"""
    pass


class DeviceErrorError(Exception):
    """Raised when a method of a device in Error state is called"""
    pass


class UnknownDeviceError(Exception):
    """Raised when a device is not known"""
    pass


class UnknownChannelError(Exception):
    """Raised when a requested channel does not exist on the device"""
    pass


class AddressInUseError(Exception):
    """Raised when a device is requested with an address, that is used by another device already"""
    pass
