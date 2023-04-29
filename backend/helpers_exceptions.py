import time
from abc import ABC, abstractmethod
from collections import defaultdict

from twisted.python import failure


class WrongStateError(Exception):
    """Raised when some Action is not possible in current State."""


class IObserver(ABC):
    @abstractmethod
    def update(self, observable, observable_key, updated_value, timestamp):
        raise NotImplementedError


class IObservable(ABC):
    observables: dict = None

    @abstractmethod
    def subscribe(self, observer: IObserver):
        raise NotImplementedError

    @abstractmethod
    def unsubscribe(self, observer: IObserver):
        raise NotImplementedError

    @abstractmethod
    def get_updates(
            self,
            variable_name: str,
            from_timestamp: float = None,
            to_timestamp: float = time.time()
    ) -> tuple[tuple[float, float | str | failure.Failure]]:
        raise NotImplementedError

    @abstractmethod
    def get_latest_update(self, variable_name: str) -> tuple[float, float | str | failure.Failure]:
        raise NotImplementedError


class IState(ABC):
    time_entered: float

    @abstractmethod
    def enter(self):
        raise NotImplementedError

    @abstractmethod
    def new_state(self, stateclass):
        raise NotImplementedError


class BaseObservable(IObservable, ABC):
    def __init__(self, *args, **kwargs):
        self._subscribers = []
        self.observables: dict[str, list[tuple[float, float | str]]] = None
        self.reset_observables()
        super().__init__(*args, **kwargs)

    def subscribe(self, observer: IObserver):
        self._subscribers.append(observer)

    def unsubscribe(self, observer: IObserver):
        try:
            self._subscribers.remove(observer)
        except ValueError:
            pass

    def reset_observables(self):
        self.observables = defaultdict(list)

    def update_subscribers(self, observable_key, updated_value, timestamp):
        for subscriber in self._subscribers:
            subscriber.update(self, observable_key, updated_value, timestamp)

    def update_observables(self, observables: dict, timestamp: float = time.time()):
        for key, value in observables.items():
            self.observables[key].append((timestamp, value))
            self.update_subscribers(key, value, timestamp)

    def get_updates(
        self,
        variable_name: str,
        from_timestamp: float = None,
        to_timestamp: float = None
    ) -> list[tuple[float, float | str | failure.Failure]]:
            updates = []
            from_timestamp = from_timestamp or 0
            to_timestamp = to_timestamp or time.time()
            for time_value_pair in self.observables[variable_name]:
                if from_timestamp < time_value_pair[0] <= to_timestamp:
                    updates.append(time_value_pair)
            return updates

    def get_latest_update(self, variable_name: str) -> tuple[float, float | str | failure.Failure]:
        return self.observables[variable_name][-1]


class StateMachineMixIn:
    def __init__(self, *args, initial_stateclass=None, **kwargs):
        self._state = None if initial_stateclass is None else initial_stateclass(self)
        self.log.info(f"{self} was initialized with state: {self._state.__class__.__name__}")
        super().__init__(*args, **kwargs)

    def set_state(self, result, state: IState):
        """
        Convenience method to use in callbacks and reactor.callLater.
        :param result:
        :param state: Class of state to set.
        :return:
        """
        self.state = state
        return result

    @property
    def state(self):
        return type(self.stateobject)  # so we can use something like 'if self.state is devicestate.NotReady'

    @state.setter
    def state(self, state_or_stateclass):
        try:
            state = state_or_stateclass(self)
        except TypeError:
            state = state_or_stateclass
        self.stateobject.new_state(state)

    @property
    def stateobject(self) -> IState:
        return self._state

    @stateobject.setter
    def stateobject(self, state):
        self._state = state
        self.log.info(f"State of {self} changed to: {state.__class__.__name__}")
        self._state.time_entered = time.time()
        self._state.enter()
        if isinstance(self, IObservable):
            self.update_observables({"state": state.__class__.__name__})
