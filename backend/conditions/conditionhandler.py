from collections import defaultdict
import time

from twisted.internet import defer, reactor
from twisted.logger import Logger

from backend.helpers_exceptions import IObserver, IObservable
from backend.conditions import ABCondition


class ConditionHandler(IObserver):
    def __init__(self, devices_and_channels: list[IObservable] | None = None):
        self._observed_objects = []
        self.log = Logger(namespace="Condition Handler")
        self._busy = False
        if devices_and_channels is not None:
            for device_or_channel in devices_and_channels:
                self.add_observable(device_or_channel)
        self._conditions: dict[ABCondition, list[defer.Deferred]] = defaultdict(list)

    def add_observable(self, observable):
        self._observed_objects.append(observable)
        observable.subscribe(self)

    def add_condition(self, condition: ABCondition, deferred: defer.Deferred = None) -> defer.Deferred:
        deferred = deferred or defer.Deferred()
        self._conditions[condition].append(deferred)
        for observable in condition.observable_objects:
            if not observable in self._observed_objects:
                self.add_observable(observable) 
        condition.start()
        return deferred

    def remove_deferred_for_condition(self, deferred: defer.Deferred, condition: ABCondition):
        deferreds = self._conditions[condition]
        deferreds.remove(deferred)
        if len(deferreds) == 0:
            self._conditions.pop(condition)


    def check_conditions_and_callback(self, condition_dict):
        if not self._busy:
            true_conditions = []
            for condition, deferred in condition_dict.items():
                if condition():
                    true_conditions.append(condition)
            if true_conditions:
                self._busy = True
                for condition in true_conditions:
                    deferreds = self._conditions.pop(condition)
                    self.log.info(f"Calling back {deferreds} due to {condition}")
                    for deferred in deferreds:
                        deferred.callback(None)
                self._busy = False
                self.check_conditions_and_callback(self._conditions)

    def update(self, observable, observable_key, updated_value, timestamp):
        if not self._busy:
            conditions_to_check = {}
            for condition, deferreds in self._conditions.items():
                if observable in condition.observable_objects:
                    conditions_to_check[condition] = deferreds
            self.check_conditions_and_callback(conditions_to_check)