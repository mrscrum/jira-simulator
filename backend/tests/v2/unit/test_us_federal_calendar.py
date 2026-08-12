import pickle
from calendar import monthcalendar
from copy import copy, deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.v2.domain.canonical_json import canonical_json
from app.v2.domain.team_blueprint import ResolvedTeamBlueprint
from app.v2.domain.us_federal_calendar import (
    HolidayHorizon,
    extend_us_federal_horizon,
    materialize_us_federal_horizon,
)

PROFILE = "US_FEDERAL_V1"
VERSION = "1"
LOS_ANGELES = "America/Los_Angeles"
KIRITIMATI = "Pacific/Kiritimati"
UTC_TIMEZONE = "Etc/UTC"
REFERENCE_FIXED_DATES = ((1, 1), (6, 19), (7, 4), (11, 11), (12, 25))
REFERENCE_WEEKDAY_RULES = (
    (1, 0, 3),
    (2, 0, 3),
    (9, 0, 1),
    (10, 0, 2),
    (11, 3, 4),
)


def _horizon() -> HolidayHorizon:
    return materialize_us_federal_horizon(
        datetime(2026, 8, 13, 9, tzinfo=UTC), LOS_ANGELES
    )


def _observation_horizon() -> HolidayHorizon:
    return materialize_us_federal_horizon(
        datetime(2022, 1, 1, tzinfo=UTC), UTC_TIMEZONE
    )


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


def test_materialization_uses_the_resolved_team_timezone_year():
    canonical_boundary = datetime(2026, 1, 1, 7, 30, tzinfo=UTC)

    los_angeles = materialize_us_federal_horizon(canonical_boundary, LOS_ANGELES)
    kiritimati = materialize_us_federal_horizon(canonical_boundary, KIRITIMATI)

    assert (los_angeles.starts_on, los_angeles.ends_on) == (
        date(2024, 1, 1),
        date(2035, 12, 31),
    )
    assert (kiritimati.starts_on, kiritimati.ends_on) == (
        date(2025, 1, 1),
        date(2036, 12, 31),
    )


def test_resolved_kiritimati_boundary_uses_team_zone_after_utc_normalization(
    blueprint_document: dict[str, object],
):
    document = deepcopy(blueprint_document)
    document["team"]["timezone"] = KIRITIMATI
    document["scrum"]["first_boundary"] = "2026-01-01T00:30:00+14:00"
    blueprint = ResolvedTeamBlueprint.from_canonical_json(canonical_json(document))

    assert blueprint.scrum.first_boundary == datetime(2025, 12, 31, 10, 30, tzinfo=UTC)
    horizon = materialize_us_federal_horizon(
        blueprint.scrum.first_boundary, blueprint.team.timezone
    )
    assert (horizon.starts_on, horizon.ends_on) == (
        date(2025, 1, 1),
        date(2036, 12, 31),
    )


def test_materialization_is_independent_of_equivalent_input_offset_representation():
    canonical_boundary = datetime(2025, 12, 31, 10, 30, tzinfo=UTC)
    positive_offset = datetime(
        2026, 1, 1, 0, 30, tzinfo=timezone(timedelta(hours=14))
    )

    assert materialize_us_federal_horizon(
        canonical_boundary, KIRITIMATI
    ) == materialize_us_federal_horizon(positive_offset, KIRITIMATI)


@pytest.mark.parametrize("first_start", [datetime(2026, 1, 1), "2026-01-01", None])
def test_materialization_rejects_naive_or_non_datetime_start(first_start: object):
    with pytest.raises((TypeError, ValueError)):
        materialize_us_federal_horizon(first_start, LOS_ANGELES)


def test_materialization_rejects_loadable_non_iana_posixrules_zone():
    ZoneInfo("posixrules")

    with pytest.raises(ValueError, match="IANA timezone"):
        materialize_us_federal_horizon(datetime(2026, 1, 1, tzinfo=UTC), "posixrules")


@pytest.mark.parametrize("timezone_name", [LOS_ANGELES, KIRITIMATI, UTC_TIMEZONE])
def test_materialization_accepts_real_available_iana_timezone_keys(timezone_name: str):
    horizon = materialize_us_federal_horizon(
        datetime(2026, 8, 13, 9, tzinfo=UTC), timezone_name
    )

    assert (horizon.profile, horizon.version) == (PROFILE, VERSION)


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


def _observed_reference(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _nth_weekday_reference(year: int, rule: tuple[int, int, int]) -> date:
    month, weekday, ordinal = rule
    weeks = monthcalendar(year, month)
    candidates = [week[weekday] for week in weeks if week[weekday]]
    return date(year, month, candidates[ordinal - 1])


def _last_monday_reference(year: int) -> date:
    candidates = [week[0] for week in monthcalendar(year, 5) if week[0]]
    return date(year, 5, candidates[-1])


def _reference_holidays(year: int) -> set[date]:
    fixed = {
        _observed_reference(date(year, month, day))
        for month, day in REFERENCE_FIXED_DATES
    }
    weekdays = {
        _nth_weekday_reference(year, rule) for rule in REFERENCE_WEEKDAY_RULES
    }
    return fixed | weekdays | {_last_monday_reference(year)}


def test_federal_rules_match_independent_calendar_reference_from_1900_to_2100():
    horizon = materialize_us_federal_horizon(
        datetime(1901, 6, 1, tzinfo=UTC), UTC_TIMEZONE
    )
    horizon = extend_us_federal_horizon(horizon, date(2099, 1, 2))
    actual = {day for day in horizon.holidays if 1900 <= day.year <= 2100}
    expected = {
        day
        for year in range(1899, 2102)
        for day in _reference_holidays(year)
        if 1900 <= day.year <= 2100
    }

    assert actual == expected


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


def test_far_stale_extension_catches_up_once_and_replay_is_identity():
    horizon = _horizon()

    extended = extend_us_federal_horizon(horizon, date(2045, 1, 2))

    assert extended.ends_on == date(2056, 12, 31)
    assert extended.holidays[: len(horizon.holidays)] == horizon.holidays
    assert extend_us_federal_horizon(extended, date(2045, 1, 2)) is extended
    assert extended.ends_on.year - 2045 >= 2


def _invalid_canonical_us_horizons() -> tuple[HolidayHorizon, ...]:
    canonical = _horizon()
    missing = replace(canonical, holidays=canonical.holidays[1:])
    extra = replace(
        canonical,
        holidays=tuple(sorted((*canonical.holidays, date(2026, 7, 4)))),
    )
    noncanonical = replace(
        canonical,
        holidays=tuple(
            sorted(
                date(2026, 7, 4) if day == date(2026, 7, 3) else day
                for day in canonical.holidays
            )
        ),
    )
    partial_start = replace(
        canonical,
        starts_on=date(2025, 2, 1),
        holidays=tuple(day for day in canonical.holidays if day >= date(2025, 2, 1)),
    )
    partial_end = replace(
        canonical,
        ends_on=date(2036, 11, 30),
        holidays=tuple(day for day in canonical.holidays if day <= date(2036, 11, 30)),
    )
    return missing, extra, noncanonical, partial_start, partial_end


def test_extension_rejects_unauthenticated_us_horizon_before_threshold_check():
    for horizon in _invalid_canonical_us_horizons():
        snapshot = (horizon.starts_on, horizon.ends_on, horizon.holidays)

        with pytest.raises(ValueError, match="canonical US_FEDERAL_V1 horizon"):
            extend_us_federal_horizon(horizon, date(2026, 1, 1))

        assert (horizon.starts_on, horizon.ends_on, horizon.holidays) == snapshot


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
