from collections import defaultdict
from twisted.internet import defer

from backend.conditions.conditions import DevicesWaitingCondition
from .experiment import Experiment, Subexperiment, Failed
from backend.conditions.conditionfactory import ConditionFactory

from .helpers_exceptions import ParameterError


class ExperimentFactory:
    def __init__(self, setup, experimentconfig: dict, experiment_name: str):
        self.setup = setup
        self.experiment_name = experiment_name
        self.commandconfig = []
        self.experiment_parameter_details = experimentconfig["parameters"] or {}
        self.experiment_observable_details = experimentconfig["observables"] or []
        self.stopcondition_parameters = experimentconfig["stopconditions"] or []
        self.condition_parameters = experimentconfig["conditions"] or {}

        self.devices_and_channels = {}

        commandconfig = experimentconfig["commands"]
        # collecting all devices and channels
        for i, command_or_subexp in enumerate(commandconfig):
            if len(command_or_subexp) == 4:
                devicename = command_or_subexp[0]
                if devicename not in self.devices_and_channels.keys():
                    self.devices_and_channels[devicename] = self.setup.devices_and_channels[devicename]
            else:
                other_experimentfactory = self.setup.experimentfactories[command_or_subexp[0]]
                for details in other_experimentfactory.experiment_observable_details:
                    if details not in self.experiment_observable_details:
                        self.experiment_observable_details.append(details)
                for devicename, device in other_experimentfactory.devices_and_channels.items():
                    if device not in self.devices_and_channels.values():
                        self.devices_and_channels[devicename] = device

        # then get commandconfig ready
        for command_or_subexp in commandconfig:
            if len(command_or_subexp) == 4:
                device = self.devices_and_channels[command_or_subexp[0]]
                method = getattr(device, command_or_subexp[1])
                self.commandconfig.append((method, command_or_subexp[2], command_or_subexp[3]))
            else:
                command_or_subexp[0] = self.setup.experimentfactories[command_or_subexp[0]]
                self.commandconfig.append(command_or_subexp)

    def _make_all_devices_wait(self, condition_title):
        condition = DevicesWaitingCondition(condition_title, list(self.setup.current_experiment.devices_and_channels.values()))
        waitcommands = []
        for device in self.setup.current_experiment.devices_and_channels.values():
            waitcommands.append(device.wait(condition))
        return waitcommands

    def _parse_value(self, value, conditionfactory, **values):
        new_value = value
        if isinstance(value, str):
            try:
                parameters = self.condition_parameters[value]
            except KeyError:
                new_value = value.format(**values)
            else:
                new_value = conditionfactory.get_condition(value, *parameters, **values)
        return new_value

    def get_stop_conditions(self, conditionfactory, **values):
        return [conditionfactory.get_condition(parameters[0], *parameters, **values) for parameters in self.stopcondition_parameters]

    def _get_experiment_parameters(self, experiment_id: str, **values):
        commandlist = []
        conditionfactory = ConditionFactory(self.setup)
        stopconditions = self.get_stop_conditions(conditionfactory, **values)
        parameters = {}
        subexperiments = []
        factory_counters = defaultdict(int)
        if len(values) == len(self.experiment_parameter_details):
            for key, value in values.items():
                parameters[key] = [value, self.experiment_parameter_details[key][1]]
        else:
            raise ParameterError(f"Given values do not match amount of parameters for {self.experiment_name}.")
        for command in self.commandconfig:
            new_args, new_kwargs = [], {}
            try:
                method, args, kwargs = command
            except ValueError:
                factory, kwargs = command
                factory_counters[factory] += 1
                for key, value in kwargs.items():
                    new_kwargs[key] = self._parse_value(value, conditionfactory, **values)
                subexp = factory.get_subexperiment(f"{experiment_id}_{factory.experiment_name}_{factory_counters[factory]}", **new_kwargs)
                subexperiments.append(subexp)
                commandlist.append(subexp)
            else:
                for value in args:
                    new_args.append(self._parse_value(value, conditionfactory, **values))
                for key, value in kwargs.items():
                    new_kwargs[key] = self._parse_value(value, conditionfactory, **values)
                commandlist.append((method, new_args, new_kwargs))
        log_name = f"{self.experiment_name} {experiment_id}"
        return self, commandlist, experiment_id, self.devices_and_channels, parameters, stopconditions, log_name, subexperiments

    def get_experiment(self, experiment_id: str = None, **values) -> Experiment:
        return Experiment(*self._get_experiment_parameters(experiment_id, **values))
    
    def get_subexperiment(self, experiment_id: str, **values) -> Subexperiment:
        return Subexperiment(*self._get_experiment_parameters(experiment_id, **values))
