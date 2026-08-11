import pickle
from copy import copy, deepcopy
from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, timedelta, timezone
from functools import partial

import pytest

from app.v2.domain.business_calendar import (
    BusinessCalendar,
    BusinessTimeAddition,
    CadenceRule,
    DualElapsed,
    UtcInterval,
    cadence_boundary,
)
from app.v2.domain.team_blueprint import CalendarBlueprint, ResolvedTeamBlueprint

TEAM_TIMEZONE = "America/Los_Angeles"
ONE_HOUR = timedelta(hours=1)
_utc = partial(datetime, tzinfo=UTC)


def _calendar_blueprint(**changes: object) -> CalendarBlueprint:
    values: dict[str, object] = {
        "working_weekdays": ("MON", "TUE", "WED", "THU", "FRI"),
        "workday_start": "09:00",
        "workday_end": "17:00",
        "holiday_calendar_profile": "CUSTOM_EXPLICIT_V1",
        "holiday_calendar_version": "1",
        "holiday_horizon_end": date(2027, 12, 31),
        "holidays": (date(2026, 12, 25),),
    }
    values.update(changes)
    return CalendarBlueprint.model_validate(values, strict=True)


def _unchecked_blueprint(**changes: object) -> CalendarBlueprint:
    valid = _calendar_blueprint().model_dump()
    valid.update(changes)
    return CalendarBlueprint.model_construct(**valid)


def _calendar(**changes: object) -> BusinessCalendar:
    return BusinessCalendar.from_blueprint(TEAM_TIMEZONE, _calendar_blueprint(**changes))


def test_utc_interval_normalizes_aware_offsets_to_utc():
    pacific_offset = timezone(timedelta(hours=-7))
    interval = UtcInterval(
        datetime(2026, 8, 10, 9, tzinfo=pacific_offset),
        datetime(2026, 8, 10, 10, tzinfo=pacific_offset),
    )

    assert interval == UtcInterval(_utc(2026, 8, 10, 16), _utc(2026, 8, 10, 17))


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (datetime(2026, 8, 10), _utc(2026, 8, 11)),
        (_utc(2026, 8, 10), datetime(2026, 8, 11)),
        (_utc(2026, 8, 11), _utc(2026, 8, 10)),
    ],
)
def test_utc_interval_rejects_naive_or_reversed_values(start: datetime, end: datetime):
    with pytest.raises(ValueError):
        UtcInterval(start, end)


def test_utc_interval_accepts_an_exact_zero_interval():
    instant = _utc(2026, 8, 10, 16)

    assert UtcInterval(instant, instant).start == instant


@pytest.mark.parametrize(
    ("calendar_elapsed", "business_elapsed"),
    [
        (timedelta(hours=-1), timedelta()),
        (timedelta(), timedelta(hours=-1)),
        (timedelta(hours=1), timedelta(hours=2)),
        ("one hour", timedelta()),
    ],
)
def test_dual_elapsed_rejects_invalid_clock_relationships(
    calendar_elapsed: object, business_elapsed: object
):
    with pytest.raises((TypeError, ValueError)):
        DualElapsed(calendar_elapsed, business_elapsed)


def test_business_time_addition_normalizes_start_and_allows_zero():
    offset = timezone(timedelta(hours=5, minutes=30))
    request = BusinessTimeAddition(datetime(2026, 8, 10, 21, 30, tzinfo=offset), timedelta())

    assert request.start == _utc(2026, 8, 10, 16)
    assert request.duration == timedelta()


@pytest.mark.parametrize(
    ("start", "duration"),
    [
        (datetime(2026, 8, 10), timedelta()),
        (_utc(2026, 8, 10), timedelta(microseconds=-1)),
        (_utc(2026, 8, 10), 1),
    ],
)
def test_business_time_addition_rejects_naive_negative_or_wrong_duration(
    start: datetime, duration: object
):
    with pytest.raises((TypeError, ValueError)):
        BusinessTimeAddition(start, duration)


@pytest.mark.parametrize("cadence_days", [True, False, 0, -1, 14.0, "14"])
def test_cadence_rule_rejects_invalid_day_count(cadence_days: object):
    with pytest.raises((TypeError, ValueError)):
        CadenceRule(_utc(2026, 3, 1, 17), cadence_days)


def test_cadence_rule_rejects_naive_anchor():
    with pytest.raises(ValueError):
        CadenceRule(datetime(2026, 3, 1, 9), 14)


@pytest.mark.parametrize("timezone_name", ["", "Mars/Olympus_Mons", True, None])
def test_calendar_rejects_invalid_iana_timezone(timezone_name: object):
    with pytest.raises((TypeError, ValueError)):
        BusinessCalendar.from_blueprint(timezone_name, _calendar_blueprint())


@pytest.mark.parametrize(
    "blueprint",
    [
        _unchecked_blueprint(working_weekdays=()),
        _unchecked_blueprint(working_weekdays=("MON", "MON")),
        _unchecked_blueprint(working_weekdays=("TUE", "MON")),
        _unchecked_blueprint(working_weekdays=("FUNDAY",)),
        _unchecked_blueprint(workday_start="9:00"),
        _unchecked_blueprint(workday_start="17:00", workday_end="09:00"),
        _unchecked_blueprint(workday_start="09:00", workday_end="09:00"),
        _unchecked_blueprint(holiday_calendar_profile=""),
        _unchecked_blueprint(holiday_calendar_version="  "),
        _unchecked_blueprint(holidays=(date(2026, 12, 25), date(2026, 12, 25))),
        _unchecked_blueprint(holidays=(date(2026, 12, 25), date(2026, 1, 1))),
        _unchecked_blueprint(holidays=(date(2028, 1, 1),)),
    ],
)
def test_calendar_factory_revalidates_the_resolved_blueprint(blueprint: CalendarBlueprint):
    with pytest.raises((TypeError, ValueError)):
        BusinessCalendar.from_blueprint(TEAM_TIMEZONE, blueprint)


def test_calendar_can_only_be_constructed_from_a_blueprint():
    with pytest.raises(TypeError, match="from_blueprint"):
        BusinessCalendar()


def test_working_interval_and_end_use_exact_local_open_close():
    calendar = _calendar()

    assert calendar.working_interval(date(2026, 8, 10)) == UtcInterval(
        _utc(2026, 8, 10, 16), _utc(2026, 8, 11)
    )
    assert calendar.business_day_end(date(2026, 8, 10)) == _utc(2026, 8, 11)


def test_nonworking_weekend_and_holiday_have_no_interval_or_end():
    calendar = _calendar()

    for day in (date(2026, 8, 15), date(2026, 12, 25)):
        assert calendar.working_interval(day) is None
        assert calendar.business_day_end(day) is None


def test_calendar_rejects_dates_beyond_its_holiday_horizon():
    calendar = _calendar()

    with pytest.raises(ValueError, match="horizon"):
        calendar.working_interval(date(2028, 1, 1))


def test_business_date_uses_team_local_date_at_midnight_boundary():
    calendar = _calendar()

    assert calendar.business_date(_utc(2026, 8, 11, 6, 59)) == date(2026, 8, 10)
    assert calendar.business_date(_utc(2026, 8, 11, 7)) == date(2026, 8, 11)


def test_business_date_rejects_naive_instant():
    with pytest.raises(ValueError):
        _calendar().business_date(datetime(2026, 8, 10, 9))


@pytest.mark.parametrize(
    ("instant", "expected"),
    [
        (_utc(2026, 8, 10, 15), _utc(2026, 8, 10, 16)),
        (_utc(2026, 8, 10, 16), _utc(2026, 8, 10, 16)),
        (_utc(2026, 8, 10, 18), _utc(2026, 8, 10, 18)),
        (_utc(2026, 8, 11), _utc(2026, 8, 11, 16)),
        (_utc(2026, 8, 15, 18), _utc(2026, 8, 17, 16)),
        (_utc(2026, 12, 25, 19), _utc(2026, 12, 28, 17)),
    ],
)
def test_next_working_instant_handles_open_close_weekend_and_holiday(
    instant: datetime, expected: datetime
):
    assert _calendar().next_working_instant(instant) == expected


def test_next_working_instant_skips_holiday_across_year_change():
    calendar = _calendar(holidays=(date(2026, 12, 25), date(2027, 1, 1)))

    assert calendar.next_working_instant(_utc(2027, 1, 1, 19)) == _utc(2027, 1, 4, 17)


def test_elapsed_counts_a_partial_workday_in_both_clocks():
    interval = UtcInterval(_utc(2026, 8, 10, 17, 30), _utc(2026, 8, 10, 19))

    assert _calendar().elapsed(interval) == DualElapsed(
        timedelta(hours=1, minutes=30), timedelta(hours=1, minutes=30)
    )


@pytest.mark.parametrize(
    ("interval", "expected_calendar", "expected_business"),
    [
        (UtcInterval(_utc(2026, 8, 10, 15), _utc(2026, 8, 11, 1)), 10, 8),
        (UtcInterval(_utc(2026, 8, 10, 23), _utc(2026, 8, 11, 17)), 18, 2),
        (UtcInterval(_utc(2026, 8, 14, 23), _utc(2026, 8, 17, 18)), 67, 3),
        (UtcInterval(_utc(2026, 8, 15, 16), _utc(2026, 8, 16, 16)), 24, 0),
        (UtcInterval(_utc(2026, 12, 25, 17), _utc(2026, 12, 26, 1)), 8, 0),
    ],
)
def test_elapsed_separates_calendar_and_business_time(
    interval: UtcInterval, expected_calendar: int, expected_business: int
):
    assert _calendar().elapsed(interval) == DualElapsed(
        timedelta(hours=expected_calendar), timedelta(hours=expected_business)
    )


def test_elapsed_treats_midnight_after_horizon_as_an_exclusive_endpoint():
    interval = UtcInterval(_utc(2027, 12, 31, 17), _utc(2028, 1, 1, 8))

    assert _calendar(holidays=()).elapsed(interval) == DualElapsed(
        timedelta(hours=15), timedelta(hours=8)
    )


@pytest.mark.parametrize(
    ("addition", "expected"),
    [
        (BusinessTimeAddition(_utc(2026, 8, 10, 15), timedelta(hours=2)), _utc(2026, 8, 10, 18)),
        (BusinessTimeAddition(_utc(2026, 8, 10, 23), ONE_HOUR), _utc(2026, 8, 11)),
        (BusinessTimeAddition(_utc(2026, 8, 11), ONE_HOUR), _utc(2026, 8, 11, 17)),
        (BusinessTimeAddition(_utc(2026, 8, 15, 18), ONE_HOUR), _utc(2026, 8, 17, 17)),
        (BusinessTimeAddition(_utc(2026, 12, 25, 18), ONE_HOUR), _utc(2026, 12, 28, 18)),
        (BusinessTimeAddition(_utc(2026, 8, 14, 23), timedelta(hours=10)), _utc(2026, 8, 18, 17)),
    ],
)
def test_add_business_time_handles_boundaries_and_multiple_dates(
    addition: BusinessTimeAddition, expected: datetime
):
    assert _calendar().add(addition) == expected


def test_add_zero_returns_normalized_input_without_calendar_adjustment():
    offset = timezone(timedelta(hours=-7))
    request = BusinessTimeAddition(datetime(2026, 8, 15, 12, tzinfo=offset), timedelta())

    assert _calendar().add(request) == _utc(2026, 8, 15, 19)


@pytest.mark.parametrize(
    "case",
    [
        (date(2026, 3, 8), _utc(2026, 3, 8, 8, 30), _utc(2026, 3, 8, 10), 1.5),
        (date(2026, 11, 1), _utc(2026, 11, 1, 7, 30), _utc(2026, 11, 1, 11), 3.5),
    ],
)
def test_working_interval_uses_exact_utc_elapsed_across_both_dst_changes(
    case: tuple[date, datetime, datetime, float],
):
    day, expected_start, expected_end, expected_hours = case
    calendar = _calendar(
        working_weekdays=("SUN",), workday_start="00:30", workday_end="03:00", holidays=()
    )
    interval = calendar.working_interval(day)

    assert interval == UtcInterval(expected_start, expected_end)
    assert calendar.elapsed(interval).business == timedelta(hours=expected_hours)


@pytest.mark.parametrize(
    "case",
    [
        (date(2026, 3, 8), "02:30", "04:00", "nonexistent"),
        (date(2026, 11, 1), "01:30", "03:00", "ambiguous"),
    ],
)
def test_calendar_rejects_nonexistent_or_ambiguous_local_boundaries(
    case: tuple[date, str, str, str],
):
    day, start, end, error = case
    calendar = _calendar(
        working_weekdays=("SUN",), workday_start=start, workday_end=end, holidays=()
    )

    with pytest.raises(ValueError, match=error):
        calendar.working_interval(day)


@pytest.mark.parametrize(
    ("anchor", "expected"),
    [
        (_utc(2026, 3, 1, 17), _utc(2026, 3, 15, 16)),
        (_utc(2026, 10, 25, 16), _utc(2026, 11, 8, 17)),
    ],
)
def test_fourteen_local_day_cadence_retains_clock_across_dst(
    anchor: datetime, expected: datetime
):
    rule = CadenceRule(anchor, 14)

    assert cadence_boundary(_calendar(), rule, 0) == anchor
    assert cadence_boundary(_calendar(), rule, 1) == expected


def test_cadence_does_not_shift_for_weekend_or_holiday():
    calendar = _calendar(holidays=(date(2026, 12, 25),))
    rule = CadenceRule(_utc(2026, 12, 11, 17), 14)

    assert cadence_boundary(calendar, rule, 1) == _utc(2026, 12, 25, 17)


@pytest.mark.parametrize("ordinal", [True, False, -1, 1.0, "1"])
def test_cadence_rejects_invalid_ordinal(ordinal: object):
    with pytest.raises((TypeError, ValueError)):
        cadence_boundary(_calendar(), CadenceRule(_utc(2026, 3, 1, 17), 14), ordinal)


@pytest.mark.parametrize(
    ("anchor", "error"),
    [
        (_utc(2026, 2, 22, 10, 30), "nonexistent"),
        (_utc(2026, 10, 18, 8, 30), "ambiguous"),
    ],
)
def test_cadence_rejects_target_local_dst_gap_or_overlap(anchor: datetime, error: str):
    with pytest.raises(ValueError, match=error):
        cadence_boundary(_calendar(), CadenceRule(anchor, 14), 1)


def test_calendar_operations_do_not_shift_resolved_first_boundary(
    resolved_blueprint_json: str,
):
    blueprint = ResolvedTeamBlueprint.from_canonical_json(resolved_blueprint_json)
    calendar = BusinessCalendar.from_blueprint(blueprint.team.timezone, blueprint.calendar)
    original_boundary = blueprint.scrum.first_boundary

    calendar.elapsed(UtcInterval(_utc(2026, 8, 10), _utc(2026, 8, 11)))
    calendar.add(BusinessTimeAddition(_utc(2026, 8, 10), ONE_HOUR))
    calendar.next_working_instant(_utc(2026, 8, 10))

    assert blueprint.scrum.first_boundary == original_boundary
    assert cadence_boundary(
        calendar, CadenceRule(original_boundary, blueprint.scrum.cadence_days), 1
    ) == _utc(2026, 8, 27, 16)
    assert blueprint.canonical_json() == resolved_blueprint_json


def test_calendar_value_objects_are_slotted_frozen_copy_stable_and_not_picklable():
    cases = (
        (UtcInterval(_utc(2026, 8, 10), _utc(2026, 8, 11)), "start"),
        (DualElapsed(timedelta(days=1), timedelta(hours=8)), "business"),
        (BusinessTimeAddition(_utc(2026, 8, 10), ONE_HOUR), "duration"),
        (CadenceRule(_utc(2026, 8, 10), 14), "cadence_days"),
        (_calendar(), "_timezone_name"),
    )

    for value, field in cases:
        with pytest.raises(TypeError):
            vars(value)
        with pytest.raises((FrozenInstanceError, TypeError)):
            setattr(value, field, None)
        assert copy(value) is value
        assert deepcopy(value) is value
        with pytest.raises(TypeError, match="reconstructed"):
            pickle.dumps(value)
