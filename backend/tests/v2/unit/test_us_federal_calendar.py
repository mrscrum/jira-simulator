import pickle
from copy import copy, deepcopy
from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from app.v2.domain.us_federal_calendar import (
    HolidayHorizon,
    extend_us_federal_horizon,
    materialize_us_federal_horizon,
)

PROFILE = "US_FEDERAL_V1"
VERSION = "1"


def _horizon() -> HolidayHorizon:
    return materialize_us_federal_horizon(datetime(2026, 8, 13, 9, tzinfo=UTC))


def _observation_horizon() -> HolidayHorizon:
    return materialize_us_federal_horizon(datetime(2022, 1, 1, tzinfo=UTC))


def test_holiday_horizon_accepts_ordered_dates_inside_its_bounds():
    horizon = HolidayHorizon(
        PROFILE,
        VERSION,
        date(2025, 1, 1),
        date(2026, 12, 31),
        (date(2025, 1, 1), date(2026, 12, 25)),
    )

    assert horizon.holidays == (date(2025, 1, 1), date(2026, 12, 25))


@pytest.mark.parametrize(
    "values",
    [
        ("", VERSION, date(2025, 1, 1), date(2026, 12, 31), ()),
        (PROFILE, " ", date(2025, 1, 1), date(2026, 12, 31), ()),
        (PROFILE, VERSION, date(2027, 1, 1), date(2026, 12, 31), ()),
        (PROFILE, VERSION, date(2025, 1, 1), date(2026, 12, 31), (date(2024, 12, 31),)),
        (PROFILE, VERSION, date(2025, 1, 1), date(2026, 12, 31), (date(2027, 1, 1),)),
        (
            PROFILE,
            VERSION,
            date(2025, 1, 1),
            date(2026, 12, 31),
            (date(2025, 1, 1), date(2025, 1, 1)),
        ),
        (
            PROFILE,
            VERSION,
            date(2025, 1, 1),
            date(2026, 12, 31),
            (date(2026, 1, 1), date(2025, 1, 1)),
        ),
        (PROFILE, VERSION, datetime(2025, 1, 1, tzinfo=UTC), date(2026, 12, 31), ()),
        (PROFILE, VERSION, date(2025, 1, 1), datetime(2026, 12, 31, tzinfo=UTC), ()),
        (PROFILE, VERSION, date(2025, 1, 1), date(2026, 12, 31), []),
    ],
)
def test_holiday_horizon_rejects_invalid_identity_bounds_or_dates(values: tuple[object, ...]):
    with pytest.raises((TypeError, ValueError)):
        HolidayHorizon(*values)


def test_materialization_uses_the_first_starts_local_calendar_year():
    local_start = datetime(2026, 1, 1, 0, 30, tzinfo=timezone(timedelta(hours=14)))

    horizon = materialize_us_federal_horizon(local_start)

    assert (horizon.profile, horizon.version) == (PROFILE, VERSION)
    assert horizon.starts_on == date(2025, 1, 1)
    assert horizon.ends_on == date(2036, 12, 31)


@pytest.mark.parametrize("first_start", [datetime(2026, 1, 1), "2026-01-01", None])
def test_materialization_rejects_naive_or_non_datetime_start(first_start: object):
    with pytest.raises((TypeError, ValueError)):
        materialize_us_federal_horizon(first_start)


def test_materialization_contains_every_exact_2026_federal_rule():
    expected = (
        date(2026, 1, 1),
        date(2026, 1, 19),
        date(2026, 2, 16),
        date(2026, 5, 25),
        date(2026, 6, 19),
        date(2026, 7, 3),
        date(2026, 9, 7),
        date(2026, 10, 12),
        date(2026, 11, 11),
        date(2026, 11, 26),
        date(2026, 12, 25),
    )

    actual = tuple(day for day in _horizon().holidays if day.year == 2026)

    assert actual == expected


def test_fixed_holidays_observe_saturday_friday_and_sunday_monday():
    holidays = _observation_horizon().holidays

    assert date(2021, 7, 5) in holidays
    assert date(2021, 12, 24) in holidays
    assert date(2026, 7, 3) in holidays
    assert date(2027, 7, 5) in holidays


def test_cross_year_new_year_observation_is_included_and_inauguration_is_excluded():
    holidays = _observation_horizon().holidays

    assert date(2021, 12, 31) in holidays
    assert date(2032, 12, 31) in holidays
    assert date(2021, 1, 20) not in holidays


def test_materialized_holidays_are_unique_ordered_and_bounded():
    horizon = _horizon()

    assert horizon.holidays == tuple(sorted(set(horizon.holidays)))
    assert all(horizon.starts_on <= day <= horizon.ends_on for day in horizon.holidays)


def test_extension_is_a_noop_when_exactly_two_complete_years_remain():
    horizon = _horizon()

    assert extend_us_federal_horizon(horizon, date(2035, 1, 1)) is horizon


def test_extension_appends_ten_years_after_threshold_and_is_idempotent():
    horizon = _horizon()

    extended = extend_us_federal_horizon(horizon, date(2035, 1, 2))

    assert extended.starts_on == date(2025, 1, 1)
    assert extended.ends_on == date(2046, 12, 31)
    assert extended.holidays[: len(horizon.holidays)] == horizon.holidays
    assert extend_us_federal_horizon(extended, date(2035, 1, 2)) is extended


@pytest.mark.parametrize(
    "horizon",
    [
        HolidayHorizon("CUSTOM_EXPLICIT_V1", VERSION, date(2025, 1, 1), date(2036, 12, 31), ()),
        HolidayHorizon(PROFILE, "2", date(2025, 1, 1), date(2036, 12, 31), ()),
    ],
)
def test_extension_rejects_non_us_federal_profile_or_version(horizon: HolidayHorizon):
    with pytest.raises(ValueError, match="US_FEDERAL_V1"):
        extend_us_federal_horizon(horizon, date(2035, 1, 2))


@pytest.mark.parametrize("as_of", [datetime(2035, 1, 2, tzinfo=UTC), "2035-01-02", None])
def test_extension_rejects_non_date_as_of(as_of: object):
    with pytest.raises(TypeError):
        extend_us_federal_horizon(_horizon(), as_of)


def test_holiday_horizon_is_slotted_frozen_copy_stable_and_not_picklable():
    horizon = _horizon()

    with pytest.raises(TypeError):
        vars(horizon)
    with pytest.raises(FrozenInstanceError):
        horizon.ends_on = date(2037, 12, 31)
    assert copy(horizon) is horizon
    assert deepcopy(horizon) is horizon
    with pytest.raises(TypeError, match="reconstructed"):
        pickle.dumps(horizon)
