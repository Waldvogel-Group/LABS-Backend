from collections import ChainMap, defaultdict
from pathlib import Path
import time
import sys

from twisted.internet import defer, reactor
from twisted.logger import (textFileLogObserver, FilteringLogObserver, LogLevelFilterPredicate, LogLevel,
                            globalLogBeginner, Logger, jsonFileLogObserver)

from backend.devices.devicefactory import DeviceFactory
from backend.experiments import experimentstates
from backend.experiments.experimentfactory import ExperimentFactory
from backend.helpers_exceptions import IObserver, StateMachineMixIn, BaseObservable
from .setupstates import *
from .setuptofrontend import SetupChannelFactory
from backend.conditions.conditionhandler import ConditionHandler


def initialize_logger(level, filename):
    filter_predicate = LogLevelFilterPredicate(defaultLogLevel=LogLevel.levelWithName(level))

    json_observer = jsonFileLogObserver(open(filename, "w"))
    json_observer = FilteringLogObserver(json_observer, [filter_predicate])

    app_observer = textFileLogObserver(sys.stdout)
    app_observer = FilteringLogObserver(app_observer, [filter_predicate])
    globalLogBeginner.beginLoggingTo([app_observer, json_observer])


class Setup(IObserver, StateMachineMixIn, BaseObservable):
    listenTCP = reactor.listenTCP

    def __init__(self, config: dict):
        self.config = config
        logpath = Path("logs/")
        logpath.mkdir(parents=True, exist_ok=True)
        initialize_logger(self.config["log_level"], logpath / "log.json")
        self.log = Logger(namespace="Experimental Setup")
        self.conditionhandler = ConditionHandler()
        super().__init__(initial_stateclass=Initializing)
        self.experimentfactories = {}
        self._devices = {}
        self._channels = {}
        self.experiments = {}
        self.experiment_id_order = []
        self._current_experiment_index = -1
        self._frontend_server = SetupChannelFactory(self)
        self.listenTCP(int(self.config["listen port"]), self._frontend_server)
        self.devices_and_channels = ChainMap(self._devices, self._channels)
        self._device_factory = DeviceFactory()
        deferred_devices = []
        for name, parameters in self.config["devices"].items():
            deferred_devices.append(self.get_device_or_channel(name, parameters))

        deferred_devices = defer.DeferredList(deferred_devices)
        deferred_devices.addCallback(self._get_experimentfactories)
        deferred_devices.addCallback(self.set_state, Paused)

    @property
    def current_experiment(self):
        try:
            return self.stateobject.get_current_experiment()
        except IndexError:
            return None

    @property
    def current_experiment_index(self):
        return self._current_experiment_index

    @current_experiment_index.setter
    def current_experiment_index(self, new_index: int):
        if new_index >= len(self.experiment_id_order):
            raise IndexError
        else:
            self._current_experiment_index = new_index
    
    def remote_start(self):
        return self.start()

    def remote_stop(self):
        if self.current_experiment is None:
            for device in self.devices_and_channels.values():
                device.stop()
        else:
            self.current_experiment.state = experimentstates.Stopped
        self.state = Stopped

    def remote_pause(self):
        pass

    def remote_shutdown(self):
        for device in self._devices.values():
            device.shutdown()

    def remote_insert_experiment_after(self, existing_id: str, experiment_id: str, experiment_type: str, **kwargs):
        return self.insert_experiment_after(existing_id, experiment_id, experiment_type, **kwargs)

    def remote_add_experiment(self, experiment_id: str, experiment_type: str, **kwargs):
        return self.add_experiment(experiment_id, experiment_type, **kwargs)

    def remote_station_overview(self):
        try:
            return {
                "status": self.state.__name__,
                "running_experiment_name": self.current_experiment.id,
                "total_experiments_queued": len(self.experiment_id_order),
                "current_run_number": self.current_experiment_index + 1
            }
        except AttributeError:
            return {
                "status": self.state.__name__,
                "running_experiment_name": "",
                "total_experiments_queued": len(self.experiment_id_order),
                "current_run_number": ""
            }

    def remote_get_experiment_types(self):
        experiment_types = {}
        for experiment_type, experiment_factory in self.experimentfactories.items():
            experiment_types[experiment_type] = {
                "parameters": experiment_factory.experiment_parameter_details,
                "observables": experiment_factory.experiment_observable_details
            }
        return experiment_types

    def remote_station_run_tables(self):
        experiments = []
        for id, experiment in self.experiments.items():
            data = {
                "name": id,
                "type": experiment.factory.experiment_name,
                "parameters": experiment.parameters,
                "state": experiment.state.__name__
            }
            experiments.append(data)
        return experiments

    def remote_get_updates(self, component_observable_pairs: Optional[dict] = None, from_timestamp: Optional[str] = None, to_timestamp: Optional[str] = None):
        response = {"timestamp": time.time()}
        from_timestamp = float(from_timestamp) if from_timestamp is not None else None
        to_timestamp = float(to_timestamp) if to_timestamp is not None else None
        if self.current_experiment is None:
            response["current_experiment"] = ""
            response["experiment_started"] = ""
        else:
            response["current_experiment"] = self.current_experiment.id
            response["experiment_started"] = self.current_experiment.starting_time
        if component_observable_pairs is None:
            component_observable_pairs = defaultdict(list)
            if self.current_experiment is None:
                component_observable_pairs = {device: [] for device in self.devices_and_channels.keys()}
            else:
                for observable_detail in self.current_experiment.observable_details:
                    component_observable_pairs[observable_detail[0]].append(observable_detail[1])
        updates = response["updates"] = defaultdict(dict)
        for componentname, observablenames in component_observable_pairs.items():
            for observablename in observablenames:
                updates[componentname][observablename] = self.devices_and_channels[componentname].get_updates(
                    observablename, from_timestamp, to_timestamp)
        return response

    def remote_station_components(self):
        components_list = []
        for name, device_or_channel in self.devices_and_channels.items():
            component_details = {
                    "component_name": name,
                    "component_log_name": device_or_channel.log_name, 
                    "component_address": device_or_channel.full_address                  
                }
            try:
                component_details["channel"] = device_or_channel.channel
            except AttributeError:
                pass
            components_list.append(component_details)
        return components_list

    def get_device_or_channel(self, name, parameters):
        deferred_device_or_channel = self._device_factory.construct_device(conditionhandler=self.conditionhandler,
                                                                           **parameters)

        def observe_and_add(device_or_channel, name):
            device_or_channel.subscribe(self)
            self.conditionhandler.add_observable(device_or_channel)
            try:
                device = device_or_channel.device
            except AttributeError:
                device = device_or_channel
            else:
                self._channels[name] = device_or_channel
                name = f"{parameters['driver']} {parameters['address']}"
                device.subscribe(self)
            self._devices[name] = device
            return device_or_channel
        return deferred_device_or_channel.addCallback(observe_and_add, name)

    def _get_experimentfactories(self, result):
        for name, experimentconfig in self.config["experiments"].items():
            self.experimentfactories[name] = ExperimentFactory(self, experimentconfig, name)
        return result

    def _get_conditions(self, result):
        return result

    def insert_experiment_after(self, existing_id: str, experiment_id: str, experiment_type: str, **kwargs):
        return self.stateobject.insert_experiment_after(existing_id, experiment_id, experiment_type, **kwargs)

    def add_experiment(self, experiment_id: str, experiment_type: str, **kwargs):
        return self.insert_experiment_after(None, experiment_id, experiment_type, **kwargs)

    def start(self):
        if self.state == Paused or self.state == Stopped:
            self.state = Ready

    def execute_experiment(self, experiment):
        def stop_observing(result, experiment):
            experiment.unsubscribe(self)
            return result
        for device in self.devices_and_channels.values():
            device.reset_observables()
        experiment.subscribe(self)
        deferred = experiment.execute()
        deferred.addBoth(stop_observing, experiment)
        deferred.addCallbacks(self.set_state, self.set_state, callbackArgs=[Ready], errbackArgs=[Failed])

    def update(self, observable, observable_key, updated_value, timestamp):
        pass