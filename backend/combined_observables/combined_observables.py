import time
from abc import ABC
from py_expression_eval import Parser

from backend.helpers_exceptions import IObservable, IObserver
from backend.devices.base import AbstractBaseDevice


class ABCombinedObservable(IObserver, ABC):
    observable: IObservable
    starting_time: float

    def start(self):
        self.observable.subscribe(self)
        self.starting_time = time.time()

    def stop(self):
        self.observable.unsubscribe(self)


class TimeIntegral(ABCombinedObservable):
    def __init__(self, observable: AbstractBaseDevice, name: str, observable_key: str):
        self.observable = observable
        self.observable_key = observable_key
        self.name = name
        self.starting_time = None
        self.combined_observable = []

    def start(self):
        super().start()
        self.combined_observable = self._initial_values()

    def _update_integral(self, time_value_pair, last_time_value_pair=None):
        last_time_value_pair = last_time_value_pair or self.combined_observable[-1]
        last_timestamp, last_value = last_time_value_pair
        last_value = float(last_value)
        timestamp, value = time_value_pair
        time_passed = timestamp - last_timestamp
        try:
            new_integral = time_passed * float(value)
        except ValueError:
            new_integral = 0
        value = new_integral + last_value
        self.observable.update_observables({self.name: str(value)}, timestamp)
        return str(value)

    def _initial_values(self):
        observable_values = self.observable.get_updates(
            self.observable_key, self.starting_time)
        if observable_values:
            last_time_value_pair = (self.starting_time, "0")
            initial_values = []
            for time_value_pair in observable_values:
                timestamp, _ = time_value_pair
                initial_values.append((timestamp, self._update_integral(
                    time_value_pair, last_time_value_pair)))
                last_time_value_pair = time_value_pair
            return initial_values
        else:
            return [(self.starting_time, 0)]

    def update(self, observable, observable_key, updated_value, timestamp):
        if observable_key == self.observable_key:
            new_integral = self._update_integral((timestamp, updated_value))
            self.combined_observable.append((timestamp, new_integral))


class MathExpression(ABCombinedObservable):
    def __init__(self, observable: AbstractBaseDevice, name: str, expression: str):
        # e.g. '(25 - dosed_volume)/3' where dosed_volume would be a observable_key
        self.expression = Parser().parse(expression)
        self.name = name
        self.observable = observable
        self.newest_timestamp = 0

    def update(self, observable, observable_key, updated_value, timestamp):
        if observable_key in self.expression.variables():
            if timestamp > self.newest_timestamp:
                try:
                    self.newest_timestamp = timestamp
                    last_values = {variable: float(self.observable.get_latest_update(
                        variable)[1]) for variable in self.expression.variables()}
                    result = self.expression.evaluate(last_values)
                    self.observable.update_observables(
                        {self.name: str(result)}, timestamp)
                except IndexError:
                    pass
