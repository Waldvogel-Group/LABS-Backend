class SetupStateError(Exception):
    """Raised when the requested action is not applicable in the current state."""
    pass


class NonUniqueIDError(Exception):
    """Raised when the given ID is not unique."""
    pass


class ExperimentOrderError(Exception):
    """Raised when the Experiment cannot be inserted at a given index."""
    pass
