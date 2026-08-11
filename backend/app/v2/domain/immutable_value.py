"""Shared ordinary-immutability policy for deterministic value objects."""

from dataclasses import dataclass
from typing import NoReturn, Self

RECONSTRUCTION_ERROR = "deterministic value objects cannot be pickled or reconstructed"


def _reject_reconstruction() -> NoReturn:
    raise TypeError(RECONSTRUCTION_ERROR)


class ImmutableValue:
    __slots__ = ()

    def __copy__(self) -> Self:
        return self

    def __deepcopy__(self, _memo: dict[int, object]) -> Self:
        return self

    def __reduce__(self) -> NoReturn:
        _reject_reconstruction()

    def __reduce_ex__(self, _protocol: int) -> NoReturn:
        _reject_reconstruction()

    def __getstate__(self) -> NoReturn:
        _reject_reconstruction()

    def __setstate__(self, _state: object) -> NoReturn:
        _reject_reconstruction()


def immutable_dataclass(value_type: type) -> type:
    immutable_type = dataclass(frozen=True, slots=True)(value_type)
    immutable_type.__getstate__ = ImmutableValue.__getstate__
    immutable_type.__setstate__ = ImmutableValue.__setstate__
    return immutable_type
