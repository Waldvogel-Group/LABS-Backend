from abc import ABC
import time

from backend.helpers_exceptions import IState


class ExperimentState(IState, ABC):
    def __init__(self, experiment):
        self.experiment = experiment

    def enter(self):
        pass

    def new_state(self, state):
        self.experiment.stateobject = state


class Waiting(ExperimentState):
    pass


class Running(ExperimentState):
    def enter(self):
        self.experiment.start_log_observer()
        self.experiment.starting_time = time.time()
        for device in self.experiment.devices_and_channels.values():
            device.subscribe(self.experiment)

class Finished(ExperimentState):
    def enter(self):
        self.experiment.finishing_time = time.time()  
        self.experiment.finish_experiment()      

class Failed(ExperimentState):
    def enter(self):
        self.experiment.stop()
        self.experiment.finish_experiment()


class Stopped(Failed): pass
