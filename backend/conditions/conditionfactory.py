from twisted.internet import defer

from backend.conditions import conditions


class ConditionFactory:
    def __init__(self, setup):
        self.setup = setup
        self.conditions = {}

    def get_condition(self, name, classname, args, kwargs, **experimental_parameters) -> conditions.ABCondition:
        try:
            condition = self.conditions[name]
        except KeyError:
            conditionclass = getattr(conditions, classname)
            condition = self.conditions[name] = conditionclass.from_configsnippet(self.setup, args, kwargs, **experimental_parameters)
        return condition
