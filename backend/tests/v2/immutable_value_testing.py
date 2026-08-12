"""Test-only construction of pickle state that bypasses public initializers."""

import pickle


def _new_unvalidated(value_type: type) -> object:
    return object.__new__(value_type)


class _TamperedValue:
    __slots__ = ("state", "value_type")

    def __init__(self, value_type: type, state: dict[str, object]) -> None:
        self.value_type = value_type
        self.state = state

    def __reduce__(self) -> tuple[object, tuple[type], dict[str, object]]:
        return _new_unvalidated, (self.value_type,), self.state


def tampered_pickle(value_type: type, state: dict[str, object]) -> bytes:
    return pickle.dumps(_TamperedValue(value_type, state))
