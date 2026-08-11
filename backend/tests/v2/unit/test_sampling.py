import math
from dataclasses import FrozenInstanceError

import pytest

from app.v2.domain.sampling import (
    DwellAnchors,
    TouchBounds,
    dwell_anchors,
    sample_dwell,
    sample_touch,
    touch_bounds,
)
from app.v2.domain.team_blueprint import ResolvedTeamBlueprint


def test_dwell_returns_every_exact_configured_anchor():
    anchors = DwellAnchors(1.0, 2.0, 3.0, 5.0, 6.0)

    samples = tuple(
        sample_dwell(anchors, unit_draw).sampled_hours
        for unit_draw in (0.0, 0.25, 0.50, 0.99, 1.0)
    )

    assert samples == (1.0, 2.0, 3.0, 5.0, 6.0)


@pytest.mark.parametrize(
    ("unit_draw", "expected"),
    [
        (0.125, 1.449489742783178),
        (0.375, 2.4641016151377544),
        (0.75, 3.9192905071232917),
        (0.995, 5.48074069840786),
    ],
)
def test_dwell_uses_log1p_linear_interpolation_between_anchors(
    unit_draw: float, expected: float
):
    anchors = DwellAnchors(1.0, 2.0, 3.0, 5.0, 6.0)

    sample = sample_dwell(anchors, unit_draw)

    assert sample.sampled_hours == pytest.approx(expected, rel=1e-15)


def test_dense_dwell_samples_are_monotone_and_bounded_across_all_segments():
    anchors = DwellAnchors(0.25, 1.0, 4.0, 40.0, 400.0)

    values = tuple(sample_dwell(anchors, index / 1000).sampled_hours for index in range(1001))

    assert values[0] == anchors.minimum
    assert values[-1] == anchors.maximum
    assert all(anchors.minimum <= value <= anchors.maximum for value in values)
    assert all(left <= right for left, right in zip(values, values[1:], strict=False))


def test_dwell_supports_all_zero_and_equal_anchor_profiles():
    zero = DwellAnchors(0, 0, 0, 0, 0)
    equal = DwellAnchors(7.5, 7.5, 7.5, 7.5, 7.5)

    zero_values = tuple(sample_dwell(zero, draw).sampled_hours for draw in (0, 0.31, 1))
    equal_values = tuple(sample_dwell(equal, draw).sampled_hours for draw in (0, 0.31, 1))

    assert zero_values == (0.0, 0.0, 0.0)
    assert equal_values == (7.5, 7.5, 7.5)


@pytest.mark.parametrize(
    "anchors",
    [
        DwellAnchors(0.0, 1e-300, 1e-200, 1e-100, 1e-50),
        DwellAnchors(1e-300, 1e-200, 1e-100, 1e100, 1e300),
    ],
)
def test_dwell_supports_very_small_and_large_finite_anchors(anchors: DwellAnchors):
    values = tuple(sample_dwell(anchors, draw).sampled_hours for draw in (0.01, 0.49, 0.9, 1))

    assert all(math.isfinite(value) for value in values)
    assert all(anchors.minimum <= value <= anchors.maximum for value in values)
    assert tuple(sorted(values)) == values


@pytest.mark.parametrize("invalid_value", [True, "1", None, math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("field_index", range(5))
def test_dwell_rejects_invalid_value_in_every_anchor(
    invalid_value: object, field_index: int
):
    values: list[object] = [0.0, 1.0, 2.0, 3.0, 4.0]
    values[field_index] = invalid_value

    with pytest.raises((TypeError, ValueError)):
        DwellAnchors(*values)


@pytest.mark.parametrize("field_index", range(5))
def test_dwell_rejects_negative_value_in_every_anchor(field_index: int):
    values = [0.0, 1.0, 2.0, 3.0, 4.0]
    values[field_index] = -1.0

    with pytest.raises(ValueError):
        DwellAnchors(*values)


@pytest.mark.parametrize(
    "values",
    [
        (2.0, 1.0, 3.0, 4.0, 5.0),
        (1.0, 3.0, 2.0, 4.0, 5.0),
        (1.0, 2.0, 4.0, 3.0, 5.0),
        (1.0, 2.0, 3.0, 5.0, 4.0),
    ],
)
def test_dwell_rejects_every_unordered_adjacent_anchor(values: tuple[float, ...]):
    with pytest.raises(ValueError):
        DwellAnchors(*values)


@pytest.mark.parametrize(
    "unit_draw", [True, False, "0.5", None, math.nan, math.inf, -math.inf, -0.001, 1.001]
)
def test_dwell_rejects_invalid_explicit_unit_draw(unit_draw: object):
    with pytest.raises((TypeError, ValueError)):
        sample_dwell(DwellAnchors(0, 1, 2, 3, 4), unit_draw)


def test_touch_returns_exact_endpoints_formula_and_equal_bound():
    bounds = TouchBounds(1.0, 4.0)
    equal = TouchBounds(2.5, 2.5)

    assert sample_touch(bounds, 0).sampled_hours == 1.0
    assert sample_touch(bounds, 0.25).sampled_hours == 1.75
    assert sample_touch(bounds, 1).sampled_hours == 4.0
    assert sample_touch(equal, 0.71).sampled_hours == 2.5


@pytest.mark.parametrize(
    "values",
    [
        (True, 1.0),
        (0.0, False),
        ("0", 1.0),
        (0.0, None),
        (math.nan, 1.0),
        (0.0, math.nan),
        (math.inf, math.inf),
        (-math.inf, 1.0),
        (-1.0, 1.0),
        (0.0, -1.0),
        (2.0, 1.0),
    ],
)
def test_touch_rejects_invalid_or_unordered_bounds(values: tuple[object, object]):
    with pytest.raises((TypeError, ValueError)):
        TouchBounds(*values)


@pytest.mark.parametrize(
    "unit_draw", [True, False, "0.5", None, math.nan, math.inf, -math.inf, -0.001, 1.001]
)
def test_touch_rejects_invalid_explicit_unit_draw(unit_draw: object):
    with pytest.raises((TypeError, ValueError)):
        sample_touch(TouchBounds(1, 4), unit_draw)


def test_samples_retain_parameters_draw_and_result_as_frozen_provenance():
    anchors = DwellAnchors(1, 2, 3, 5, 6)
    bounds = TouchBounds(1, 4)
    dwell_sample = sample_dwell(anchors, 0.5)
    touch_sample = sample_touch(bounds, 0.5)

    assert (dwell_sample.parameters, dwell_sample.unit_draw, dwell_sample.sampled_hours) == (
        anchors, 0.5, 3.0,
    )
    assert (touch_sample.parameters, touch_sample.unit_draw, touch_sample.sampled_hours) == (
        bounds, 0.5, 2.5,
    )
    with pytest.raises(FrozenInstanceError):
        dwell_sample.sampled_hours = 99.0


def test_every_resolved_timing_cell_runs_through_both_pure_samplers(
    resolved_blueprint_json: str,
):
    blueprint = ResolvedTeamBlueprint.from_canonical_json(resolved_blueprint_json)

    for entry in blueprint.timing.entries:
        dwell = dwell_anchors(entry)
        touch = touch_bounds(entry)
        for unit_draw in (0.0, 0.25, 0.5, 0.99, 1.0):
            assert dwell.minimum <= sample_dwell(dwell, unit_draw).sampled_hours <= dwell.maximum
            assert touch.minimum <= sample_touch(touch, unit_draw).sampled_hours <= touch.maximum

    assert blueprint.canonical_json() == resolved_blueprint_json


def test_timing_entry_adapters_preserve_exact_configured_values(resolved_blueprint_json: str):
    entry = ResolvedTeamBlueprint.from_canonical_json(resolved_blueprint_json).timing.entries[0]

    assert dwell_anchors(entry) == DwellAnchors(1.0, 2.0, 3.0, 5.0, 6.0)
    assert touch_bounds(entry) == TouchBounds(1.0, 4.0)
