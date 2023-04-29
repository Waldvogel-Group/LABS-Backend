from typing import Callable, Optional
from collections import defaultdict
from datetime import date
from pathlib import Path
import json

from twisted.logger import FilteringLogObserver, LogLevelFilterPredicate, LogLevel, jsonFileLogObserver, globalLogPublisher, Logger, textFileLogObserver
from twisted.internet import defer

from backend.helpers_exceptions import StateMachineMixIn, IObserver, BaseObservable
from backend.conditions.conditions import DevicesWaitingCondition, DevicesStateEqualsCondition
from backend.devices import devicestate
from .experimentstates import *


class Experiment(StateMachineMixIn, BaseObservable, IObserver):
    def __init__(self, factory, commands: list[tuple[Callable, list, dict]], experiment_id: str, devices_and_channels: dict, parameters: dict, stopconditions: list, log_name: str, subexperiments: list):
        self.id = experiment_id
        self.factory = factory
        self.observable_details = factory.experiment_observable_details
        self.parameters = parameters
        self.deferred_fail = defer.Deferred().addCallback(self.set_state, Failed)
        self.stopcondition_deferreds = defaultdict(list)
        for condition in stopconditions:
            self.stopcondition_deferreds[condition].append(self.deferred_fail)
        self.starting_time: Optional[float] = None
        self.finishing_time: Optional[float] = None
        self.log_name = log_name
        self.log = Logger(namespace=self.log_name)
        self.json_log_observer = None
        self.text_log_observer = None
        self._log_path = None
        self.devices_and_channels = devices_and_channels
        self._device_to_name = {device: devicename for devicename, device in self.devices_and_channels.items()}
        self.observed_updates = {devicename: defaultdict(list) for devicename in self.devices_and_channels.keys()}
        super().__init__(initial_stateclass=Waiting)
        self.commands = commands
        self.subexperiments = subexperiments
        self.command_index = 0
        self.deferred_success = defer.Deferred()
        for exp in subexperiments:
            exp.superexperiment = self

    @property
    def log_path(self):
        if self._log_path is None:
            today = date.today()
            log_path = Path(f"logs/{today.year}/{today.month}/{today.day}/{self.id}")
            log_path.mkdir(parents=True, exist_ok=True)
            self.log.info("setting self._log_path")
            self._log_path = log_path
        return self._log_path

    def start_log_observer(self):
        filter_predicate = LogLevelFilterPredicate(defaultLogLevel=LogLevel.levelWithName(self.factory.setup.config["log_level"]))

        json_log_file = self.log_path / "log.json"
        json_observer = jsonFileLogObserver(json_log_file.open("w"))
        self.json_log_observer = FilteringLogObserver(json_observer, [filter_predicate])
        globalLogPublisher.addObserver(self.json_log_observer)

        text_log_file = self.log_path / "log.txt"
        text_observer = textFileLogObserver(text_log_file.open("w"))
        self.text_log_observer = FilteringLogObserver(text_observer, [filter_predicate])
        globalLogPublisher.addObserver(self.text_log_observer)

    def _save_observed_updates(self):
        values_file = self.log_path / "values.json"
        with values_file.open("w") as file:
            json.dump(self.observed_updates, file)

    def _stop_log_observer(self):
        globalLogPublisher.removeObserver(self.json_log_observer)
        globalLogPublisher.removeObserver(self.text_log_observer)

    def finish_experiment(self):
        self._stop_log_observer()
        self._save_observed_updates()
        for condition, deferreds in self.stopcondition_deferreds.items():
            for deferred in deferreds:
                self.factory.setup.conditionhandler.remove_deferred_for_condition(deferred, condition)
        for device in self.devices_and_channels.values():
            device.state = devicestate.Ready
            device.unsubscribe(self)

    def _stop_devices(self, result):
        condition = DevicesStateEqualsCondition(f"Devices stopped by {self.log_name}", self.devices_and_channels.values(), devicestate.Stopped)
        for device in self.devices_and_channels.values():
            device.stop()
        return self.factory.setup.conditionhandler.add_condition(condition)

    def stop(self):
        return self._stop_devices(None)

    def _commands_finished(self, result):
        return self._stop_devices(result)
    
    def _run_command(self):
        try:
            function, args, kwargs = self.commands[self.command_index]
        except TypeError:
            experiment = self.commands[self.command_index]
            self.command_index += 1
            experiment.execute().addCallback(lambda _: self._run_command())
        except IndexError:
            condition = DevicesWaitingCondition(f"Devices reached last command of {self.log_name}", list(self.devices_and_channels.values()))
            wait_commands = [device.wait for device in self.devices_and_channels.values()]
            experiment_done = defer.DeferredList([command(condition).deferred_result for command in wait_commands])
            experiment_done.addCallback(self._commands_finished)
            experiment_done.addCallback(self.set_state, Finished)
            experiment_done.addCallback(self.deferred_success.callback)
        else:
            function(*args, **kwargs)  
            self.command_index += 1
            self._run_command()
        

    def execute(self):
        self.state = Running
        for condition in self.stopcondition_deferreds.keys():
            self.factory.setup.conditionhandler.add_condition(condition, self.deferred_fail)
        self._run_command()
        return self.deferred_success.addCallback(lambda _: Finished)

    def update(self, observable, observable_key, updated_value, timestamp):
        self.observed_updates[self._device_to_name[observable]][observable_key].append((timestamp, updated_value))
        if observable_key == "state" and updated_value == "Error":
            self.state = Failed


class Subexperiment(Experiment):
    def __init__(self, *args, **kwargs):
        self.superexperiment = None  # Set by superexperiment after initialization
        super().__init__(*args, **kwargs)

    @property
    def log_path(self):
        if self._log_path is None:
            log_path = self.superexperiment.log_path / self.id
            log_path.mkdir(parents=True, exist_ok=True)
            self._log_path = log_path
        return self._log_path
    
    def _commands_finished(self, result):
        return result