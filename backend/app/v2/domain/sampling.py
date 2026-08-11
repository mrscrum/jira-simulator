"""Pure bounded dwell and touch-work duration samplers."""

import math
from dataclasses import dataclass, fields

from app.v2.domain.team_blueprint import TimingEntry

DWELL_PROBABILITIES = (0.0, 0.25, 0.50, 0.99, 1.0)


def _finite_non_negative(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{label} must be finite")
    if normalized < 0:
        raise ValueError(f"{label} must be non-negative")
    return normalized


def _unit_draw(value: object) -> float:
    draw = _finite_non_negative(value, "unit_draw")
    if draw > 1:
        raise ValueError("unit_draw must be in [0, 1]")
    return draw


def _normalized_fields(instance: object) -> tuple[float, ...]:
    return tuple(
        _finite_non_negative(getattr(instance, field.name), field.name)
        for field in fields(instance)
    )


def _store_normalized_fields(instance: object, values: tuple[float, ...]) -> None:
    for field, value in zip(fields(instance), values, strict=True):
        object.__setattr__(instance, field.name, value)


@dataclass(frozen=True)
class DwellAnchors:
    minimum: float
    p25: float
    p50: float
    p99: float
    maximum: float

    def __post_init__(self) -> None:
        values = _normalized_fields(self)
        if values != tuple(sorted(values)):
            raise ValueError("dwell anchors must be ordered")
        _store_normalized_fields(self, values)


@dataclass(frozen=True)
class TouchBounds:
    minimum: float
    maximum: float

    def __post_init__(self) -> None:
        values = _normalized_fields(self)
        if values[0] > values[1]:
            raise ValueError("touch bounds must be ordered")
        _store_normalized_fields(self, values)


@dataclass(frozen=True)
class DurationSample:
    parameters: DwellAnchors | TouchBounds
    unit_draw: float
    sampled_hours: float

    def __post_init__(self) -> None:
        if not isinstance(self.parameters, (DwellAnchors, TouchBounds)):
            raise TypeError("parameters must be dwell anchors or touch bounds")
        draw = _unit_draw(self.unit_draw)
        hours = _finite_non_negative(self.sampled_hours, "sampled_hours")
        if not self.parameters.minimum <= hours <= self.parameters.maximum:
            raise ValueError("sampled_hours must remain within the supplied parameters")
        if hours != _sampled_hours(self.parameters, draw):
            raise ValueError("sampled_hours does not match the sampling formula")
        object.__setattr__(self, "unit_draw", draw)
        object.__setattr__(self, "sampled_hours", hours)


def dwell_anchors(entry: TimingEntry) -> DwellAnchors:
    if not isinstance(entry, TimingEntry):
        raise TypeError("entry must be a TimingEntry")
    return DwellAnchors(entry.min, entry.p25, entry.p50, entry.p99, entry.max)


def touch_bounds(entry: TimingEntry) -> TouchBounds:
    if not isinstance(entry, TimingEntry):
        raise TypeError("entry must be a TimingEntry")
    return TouchBounds(entry.touch_min, entry.touch_max)


def _dwell_segment(unit_draw: float) -> tuple[int, float]:
    for index, upper_probability in enumerate(DWELL_PROBABILITIES[1:]):
        if unit_draw < upper_probability:
            lower_probability = DWELL_PROBABILITIES[index]
            position = (unit_draw - lower_probability) / (upper_probability - lower_probability)
            return index, position
    raise ValueError("interior unit draw did not match a dwell segment")


def _interpolate_log_hours(lower: float, upper: float, position: float) -> float:
    lower_log = math.log1p(lower)
    interpolated_log = lower_log + (math.log1p(upper) - lower_log) * position
    return min(upper, max(lower, math.expm1(interpolated_log)))


def _dwell_hours(anchors: DwellAnchors, unit_draw: float) -> float:
    values = (anchors.minimum, anchors.p25, anchors.p50, anchors.p99, anchors.maximum)
    if unit_draw in DWELL_PROBABILITIES:
        return values[DWELL_PROBABILITIES.index(unit_draw)]
    segment, position = _dwell_segment(unit_draw)
    return _interpolate_log_hours(values[segment], values[segment + 1], position)


def _touch_hours(bounds: TouchBounds, unit_draw: float) -> float:
    if unit_draw == 0 or bounds.minimum == bounds.maximum:
        return bounds.minimum
    if unit_draw == 1:
        return bounds.maximum
    return bounds.minimum + (bounds.maximum - bounds.minimum) * unit_draw


def _sampled_hours(parameters: DwellAnchors | TouchBounds, unit_draw: float) -> float:
    if isinstance(parameters, DwellAnchors):
        return _dwell_hours(parameters, unit_draw)
    return _touch_hours(parameters, unit_draw)


def sample_dwell(anchors: DwellAnchors, unit_draw: float) -> DurationSample:
    if not isinstance(anchors, DwellAnchors):
        raise TypeError("anchors must be DwellAnchors")
    draw = _unit_draw(unit_draw)
    return DurationSample(anchors, draw, _dwell_hours(anchors, draw))


def sample_touch(bounds: TouchBounds, unit_draw: float) -> DurationSample:
    if not isinstance(bounds, TouchBounds):
        raise TypeError("bounds must be TouchBounds")
    draw = _unit_draw(unit_draw)
    return DurationSample(bounds, draw, _touch_hours(bounds, draw))
