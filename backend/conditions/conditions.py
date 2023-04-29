from __future__ import annotations
from typing import TYPE_CHECKING

from abc import ABC, abstractmethod
from inspect import signature
import time
from itertools import zip_longest

from twisted.internet import reactor

from backend.devices import devicestate
from backend.helpers_exceptions import IObservable, BaseObservable

if TYPE_CHECKING:
    from backend.devices.base import AbstractBaseDevice


class ABCondition(ABC):
    observable_objects: list[IObservable]

    def __init__(self, title, *args, **kwargs):
        self.title = title
        self.starting_time = None
        self.started = False
        self._turned_true = False
        super().__init__(*args, **kwargs)

    def start(self):
        if not self.started:
            self.starting_time = time.time()

    def __call__(self) -> bool:
        self._turned_true = self._turned_true or self.check_condition()
        return self._turned_true
    
    def reset_status(self):
        self._turned_true = False

    def check_condition(self) -> bool:
        raise NotImplementedError

    @classmethod
    def from_configsnippet(
            cls, setup, config_args: list, config_kwargs,
            **experimental_parameters):
        def insert_experimental_parameters(value):
            try:
                new_value = value.format(**experimental_parameters)
            except AttributeError:
                return value
            else:
                return new_value
        argument_names = list(signature(cls.__init__).parameters.keys())
        argument_names.remove("self")
        if len(argument_names) < len(config_args):
            raise Exception(
                "Too many values were given for that Conditionclass")
        config_args = [insert_experimental_parameters(
            arg) for arg in config_args]
        all_config_kwargs = dict(zip_longest(
            argument_names, config_args, fillvalue=None))
        for key, value in config_kwargs.items():
            if all_config_kwargs[key] is not None:
                raise TypeError
            else:
                all_config_kwargs[key] = insert_experimental_parameters(value)
        return cls._from_config_kwargs(setup, all_config_kwargs)

    @classmethod
    @abstractmethod
    def _from_config_kwargs(cls, setup, kwargs_strings) -> ABCondition:
        return cls(**kwargs_strings)


class CombinedCondition(ABCondition):
    def __init__(self, title, *conditions):
        super().__init__(title)
        self.conditions: list[ABCondition] = conditions
        self.observable_objects = []
        for condition in self.conditions:
            self.observable_objects += condition.observable_objects

    def start(self):
        for condition in self.conditions:
            condition.start()
        return super().start()

    def check_condition(self) -> bool:
        return all((condition() for condition in self.conditions))

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__} {self.title} "
            f"{[str(condition) for condition in self.conditions]}"
        )

    @classmethod
    def from_configsnippet(
            cls, setup, config_args: list, config_kwargs,
            **experimental_parameters):
        conditions = []
        title = config_args.pop(0)
        for classname, _config_args, _config_kwargs in config_args:
            conditionclass = globals()[classname]
            conditions.append(
                conditionclass.from_configsnippet(
                    setup, _config_args,
                    _config_kwargs, **experimental_parameters)
            )
        return cls(title, *conditions)

    @classmethod
    def _from_config_kwargs(cls, setup, kwargs_strings) -> ABCondition:
        raise NotImplementedError


class OngoingCondition(ABCondition):
    def __init__(self, title, duration, condition):
        super().__init__(title)
        self.duration = duration
        self.condition: ABCondition = condition
        self.observable_objects = condition.observable_objects
        self._true_since = None
        
    def start(self):
        self.condition.start()
        return super().start()

    def check_condition(self) -> bool:
        if self.condition():
            if self._true_since is None:
                self._true_since = time.time()
            if time.time() - self._true_since >= self.duration:
                return True
            else:
                return False
        else:
            self._true_since = None
            return False

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__} {self.title} "
            f"{self.condition}"
        )

    @classmethod
    def from_configsnippet(
            cls, setup, config_args: list, config_kwargs,
            **experimental_parameters):
        title = config_args.pop(0)
        classname, _config_args, _config_kwargs = config_args
        conditionclass = globals()[classname]
        condition = conditionclass.from_configsnippet(
                setup, _config_args,
                _config_kwargs, **experimental_parameters)
        return cls(title, condition)

    @classmethod
    def _from_config_kwargs(cls, setup, kwargs_strings) -> ABCondition:
        raise NotImplementedError
    

class ObservableEqualsValueCondition(ABCondition):
    def __init__(
            self, title, observable_object: IObservable, observable_name: str,
            value: str):
        super().__init__(title)
        self.observable_objects = [observable_object]
        self.observable_name = observable_name
        self.value = value

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__} {self.title} "
            f"({self.observable_objects[0]}.{self.observable_name} == "
            f"{self.value})"
        )

    @classmethod
    def _from_config_kwargs(cls, setup, kwargs_strings) -> ABCondition:
        kwargs_strings["observable_object"] = \
            setup.devices_and_channels[kwargs_strings["observable_object"]]
        return cls(**kwargs_strings)

    def check_condition(self) -> bool:
        try:
            timestamp, value = self.observable_objects[0].get_latest_update(
                self.observable_name)
        except IndexError:
            return False
        else:
            return value == self.value and timestamp >= self.starting_time


class ObservableGreaterOrEqualValueCondition(ObservableEqualsValueCondition):
    def check_condition(self):
        try:
            timestamp, value = self.observable_objects[0].get_latest_update(
                self.observable_name)
        except IndexError:
            return False
        else:
            return (float(value) >= float(self.value)
                    and timestamp >= self.starting_time)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__} {self.title} "
            f"({self.observable_objects[0]}.{self.observable_name} >= "
            f"{self.value})"
        )


class ObservableLessOrEqualValueCondition(ObservableEqualsValueCondition):
    def check_condition(self):
        try:
            timestamp, value = self.observable_objects[0].get_latest_update(
                self.observable_name)
        except IndexError:
            return False
        else:
            return (float(value) <= float(self.value)
                    and timestamp >= self.starting_time)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__} {self.title} "
            f"({self.observable_objects[0]}.{self.observable_name} <= "
            f"{self.value})"
        )


class ObservableInsideIntervalCondition(ABCondition):
    def __init__(
            self, title, observable_object: IObservable, observable_name: str,
            lower_limit, upper_limit):
        super().__init__(title)
        self.observable_objects = [observable_object]
        self.observable_name = observable_name
        self.lower_limit = lower_limit
        self.upper_limit = upper_limit

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__} {self.title} ({self.lower_limit} < "
            f"{self.observable_objects[0]}.{self.observable_name} < "
            f"{self.upper_limit})"
        )

    @classmethod
    def _from_config_kwargs(cls, setup, kwargs_strings) -> ABCondition:
        kwargs_strings["observable_object"] = \
            setup.devices_and_channels[kwargs_strings["observable_object"]]
        return cls(**kwargs_strings)

    def check_condition(self) -> bool:
        try:
            timestamp, value = self.observable_objects[0].get_latest_update(
                self.observable_name)
        except IndexError:
            return False
        else:
            return (
                float(self.lower_limit) < float(value) < float(self.upper_limit)
                and timestamp >= self.starting_time)


class DevicesStateEqualsCondition(ABCondition):
    def __init__(
            self, title, devices: list[AbstractBaseDevice],
            target_state: devicestate.DeviceState = devicestate.Waiting):
        super().__init__(title)
        self.observable_objects = devices
        self.target_state = target_state

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__} {self.title} "
            f"({[obs.log_name for obs in self.observable_objects]}, "
            f"{self.target_state.__name__})"
        )

    def check_condition(self) -> bool:
        correct_states = True
        for device in self.observable_objects:
            correct_states = (
                correct_states and device.state == self.target_state
                and not hasattr(
                    device.stateobject, "triggered_condition")
            )
        if correct_states:
            for device in self.observable_objects:
                device.stateobject.triggered_condition = True
        return correct_states

    @classmethod
    def _from_config_kwargs(cls, setup, kwargs_strings) -> ABCondition:
        devices = [setup.devices_and_channels[devicestring] for devicestring in kwargs_strings["devices"]]
        kwargs_strings["devices"] = devices
        kwargs_strings["target_state"] = getattr(
            devicestate, kwargs_strings["target_state"])
        return cls(**kwargs_strings)


class DevicesWaitingCondition(DevicesStateEqualsCondition):
    @classmethod
    def _from_config_kwargs(cls, setup, kwargs_strings) -> ABCondition:
        kwargs_strings["target_state"] = "Waiting"
        return super()._from_config_kwargs(setup, kwargs_strings)


class TimeCondition(ABCondition, BaseObservable):
    def __init__(self, title, time_to_wait: float):
        self.observable_objects = [self]
        super().__init__(title)
        self.time_to_wait = time_to_wait
        self._done_waiting = False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} {self.title} ({self.time_to_wait} s)"

    def _done(self):
        self._done_waiting = True
        self.update_observables({"waited time": str(self.time_to_wait)})

    def start(self):
        if not self.started:
            reactor.callLater(self.time_to_wait, self._done)
            return super().start()

    def check_condition(self) -> bool:
        return self._done_waiting

    @classmethod
    def _from_config_kwargs(cls, setup, kwargs_strings) -> ABCondition:
        kwargs_strings["time_to_wait"] = float(kwargs_strings["time_to_wait"])
        return cls(**kwargs_strings)
