from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from backend.helpers_exceptions import IState
from .helpers_exceptions import SetupStateError, NonUniqueIDError, ExperimentOrderError
if TYPE_CHECKING:
    from backend.setup.setup import Setup


from abc import ABC, abstractmethod


class SetupState(IState, ABC):
    def __init__(self, setup):
        self.setup: Setup = setup

    def new_state(self, state):
        self.setup.stateobject = state

    def insert_experiment_after(self, existing_id: Optional[str], experiment_id: str, experiment_type: str, **kwargs):
        if experiment_id in self.setup.experiment_id_order:
            raise NonUniqueIDError(f"{experiment_id} already used.")
        new_index = len(self.setup.experiment_id_order)
        if existing_id is not None:
            for index, exp_id in enumerate(self.setup.experiment_order):
                if exp_id == existing_id:
                    new_index = index + 1
            if not new_index > self.setup.current_experiment_index:
                raise ExperimentOrderError("Experiment can't be inserted before current running experiment.")
        self.setup.experiment_id_order.insert(new_index, experiment_id)
        experiment = self.setup.experimentfactories[experiment_type].get_experiment(experiment_id, **kwargs)
        self.setup.experiments[experiment_id] = experiment

    def get_current_experiment(self):
        return None


class Initializing(SetupState):
    def enter(self):
        pass

    def insert_experiment_after(self, existing_id: Optional[str], experiment_id: str, experiment_type: str, **kwargs):
        raise SetupStateError("Experiment can't be added in Initializing state.")


class Ready(SetupState):
    def enter(self):
        try:
            self.setup.current_experiment_index += 1
        except IndexError:
            return
        else:
            self.setup.state = Busy
            self.setup.execute_experiment(self.setup.current_experiment)

    def insert_experiment_after(self, existing_id: Optional[str], experiment_id: str, experiment_type: str, **kwargs):
        super().insert_experiment_after(existing_id, experiment_id, experiment_type, **kwargs)
        self.enter()


class Busy(SetupState):
    def enter(self):
        pass

    def get_current_experiment(self):
        id = self.setup.experiment_id_order[self.setup.current_experiment_index]
        return self.setup.experiments[id]


class Paused(Busy):
    pass


class Shutdown(SetupState):
    def enter(self):
        pass

    def new_state(self, stateclass):
        raise SetupStateError("Setup is in shutdown state.")

    def insert_experiment_after(self, existing_id: Optional[str], experiment_id: str, experiment_type: str, **kwargs):
        raise SetupStateError("Can't add experiment, setup is in shutdown state.")


class Failed(SetupState):
    def enter(self):
        pass

    def new_state(self, stateclass):
        raise SetupStateError("Setup is in failed state.")

    def insert_experiment_after(self, existing_id: Optional[str], experiment_id: str, experiment_type: str, **kwargs):
        raise SetupStateError("Can't add experiment, setup is in failed state.")


class Stopped(SetupState):
    def enter(self):
        pass
