"""Pure materialization of the frozen US federal holiday rules."""

from calendar import monthrange
from datetime import date, datetime, timedelta

from app.v2.domain.immutable_value import ImmutableValue, immutable_dataclass

US_FEDERAL_PROFILE = "US_FEDERAL_V1"
US_FEDERAL_VERSION = "1"
START_YEAR_OFFSET = 1
INITIAL_END_YEAR_OFFSET = 10
EXTENSION_YEARS = 10
SATURDAY = 5
SUNDAY = 6
MONDAY = 0
THURSDAY = 3
NEW_YEAR = (1, 1)
JUNETEENTH = (6, 19)
INDEPENDENCE_DAY = (7, 4)
VETERANS_DAY = (11, 11)
CHRISTMAS = (12, 25)
MLK_DAY = (1, MONDAY, 3)
WASHINGTON_BIRTHDAY = (2, MONDAY, 3)
MEMORIAL_DAY = (5, MONDAY)
LABOR_DAY = (9, MONDAY, 1)
COLUMBUS_DAY = (10, MONDAY, 2)
THANKSGIVING = (11, THURSDAY, 4)


def _identifier(value: object, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f"{label} must be a non-empty identifier")
    return value


def _calendar_date(value: object, label: str) -> date:
    if type(value) is not date:
        raise TypeError(f"{label} must be a date")
    return value


def _holiday_tuple(value: object, starts_on: date, ends_on: date) -> tuple[date, ...]:
    if type(value) is not tuple or any(type(day) is not date for day in value):
        raise TypeError("holidays must be a tuple of dates")
    if value != tuple(sorted(set(value))):
        raise ValueError("holidays must be unique and ordered")
    if any(day < starts_on or day > ends_on for day in value):
        raise ValueError("holiday falls outside its horizon")
    return value


@immutable_dataclass
class HolidayHorizon(ImmutableValue):
    profile: str
    version: str
    starts_on: date
    ends_on: date
    holidays: tuple[date, ...]

    def __post_init__(self) -> None:
        _identifier(self.profile, "profile")
        _identifier(self.version, "version")
        starts_on = _calendar_date(self.starts_on, "starts_on")
        ends_on = _calendar_date(self.ends_on, "ends_on")
        if starts_on > ends_on:
            raise ValueError("holiday horizon must be ordered")
        _holiday_tuple(self.holidays, starts_on, ends_on)


def _observed(day: date) -> date:
    if day.weekday() == SATURDAY:
        return day - timedelta(days=1)
    if day.weekday() == SUNDAY:
        return day + timedelta(days=1)
    return day


def _nth_weekday(year: int, rule: tuple[int, int, int]) -> date:
    month, weekday, ordinal = rule
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + (ordinal - 1) * 7)


def _last_weekday(year: int, rule: tuple[int, int]) -> date:
    month, weekday = rule
    last = date(year, month, monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _fixed_holidays(year: int) -> tuple[date, ...]:
    return tuple(
        _observed(date(year, month, day))
        for month, day in (NEW_YEAR, JUNETEENTH, INDEPENDENCE_DAY, VETERANS_DAY, CHRISTMAS)
    )


def _holidays_for_year(year: int) -> tuple[date, ...]:
    return (
        *_fixed_holidays(year),
        _nth_weekday(year, MLK_DAY),
        _nth_weekday(year, WASHINGTON_BIRTHDAY),
        _last_weekday(year, MEMORIAL_DAY),
        _nth_weekday(year, LABOR_DAY),
        _nth_weekday(year, COLUMBUS_DAY),
        _nth_weekday(year, THANKSGIVING),
    )


def _holidays_between(starts_on: date, ends_on: date) -> tuple[date, ...]:
    candidates = {
        holiday
        for year in range(starts_on.year - 1, ends_on.year + 2)
        for holiday in _holidays_for_year(year)
        if starts_on <= holiday <= ends_on
    }
    return tuple(sorted(candidates))


def _aware_local_year(first_start: object) -> int:
    if type(first_start) is not datetime:
        raise TypeError("first_start must be a datetime")
    if first_start.tzinfo is None or first_start.utcoffset() is None:
        raise ValueError("first_start must be aware")
    return first_start.year


def materialize_us_federal_horizon(first_start: datetime) -> HolidayHorizon:
    first_year = _aware_local_year(first_start)
    starts_on = date(first_year - START_YEAR_OFFSET, 1, 1)
    ends_on = date(first_year + INITIAL_END_YEAR_OFFSET, 12, 31)
    return HolidayHorizon(
        US_FEDERAL_PROFILE,
        US_FEDERAL_VERSION,
        starts_on,
        ends_on,
        _holidays_between(starts_on, ends_on),
    )


def _is_extendable_horizon(horizon: HolidayHorizon) -> bool:
    return horizon.profile == US_FEDERAL_PROFILE and horizon.version == US_FEDERAL_VERSION


def extend_us_federal_horizon(horizon: HolidayHorizon, as_of: date) -> HolidayHorizon:
    if type(horizon) is not HolidayHorizon:
        raise TypeError("horizon must be a HolidayHorizon")
    if not _is_extendable_horizon(horizon):
        raise ValueError("horizon must use US_FEDERAL_V1 version 1")
    current_day = _calendar_date(as_of, "as_of")
    two_year_threshold = date(horizon.ends_on.year - 1, 1, 1)
    if current_day <= two_year_threshold:
        return horizon
    ends_on = date(horizon.ends_on.year + EXTENSION_YEARS, 12, 31)
    return HolidayHorizon(
        horizon.profile,
        horizon.version,
        horizon.starts_on,
        ends_on,
        _holidays_between(horizon.starts_on, ends_on),
    )
