"""Pure timezone-aware business and fixed-cadence arithmetic."""

import re
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from zoneinfo import ZoneInfo

from app.v2.domain.iana_timezone import resolve_iana_timezone
from app.v2.domain.immutable_value import ImmutableValue, immutable_dataclass
from app.v2.domain.team_blueprint import WEEKDAYS, CalendarBlueprint

LOCAL_TIME_PATTERN = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
DATETIME_RESOLUTION = timedelta.resolution
DATETIME_RANGE_ERROR = "calendar operation exceeds the supported datetime range"
ONE_DAY = timedelta(days=1)
ZERO_DURATION = timedelta()


def _convert_timezone(value: datetime, zone: tzinfo) -> datetime:
    try:
        return value.astimezone(zone)
    except OverflowError as error:
        raise ValueError(DATETIME_RANGE_ERROR) from error


def _aware_utc(value: object, label: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be an aware datetime")
    return _convert_timezone(value, UTC)


def _duration(value: object, label: str) -> timedelta:
    if type(value) is not timedelta:
        raise TypeError(f"{label} must be a timedelta")
    return value


def _calendar_date(value: object) -> date:
    if type(value) is not date:
        raise TypeError("day must be a date")
    return value


def _positive_integer(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _non_negative_integer(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


@immutable_dataclass
class UtcInterval(ImmutableValue):
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        start = _aware_utc(self.start, "start")
        end = _aware_utc(self.end, "end")
        if start > end:
            raise ValueError("UTC interval must not be reversed")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)


@immutable_dataclass
class DualElapsed(ImmutableValue):
    calendar: timedelta
    business: timedelta

    def __post_init__(self) -> None:
        calendar = _duration(self.calendar, "calendar elapsed")
        business = _duration(self.business, "business elapsed")
        if calendar < ZERO_DURATION or business < ZERO_DURATION or business > calendar:
            raise ValueError("elapsed clocks must be non-negative and ordered")


@immutable_dataclass
class BusinessTimeAddition(ImmutableValue):
    start: datetime
    duration: timedelta

    def __post_init__(self) -> None:
        start = _aware_utc(self.start, "start")
        duration = _duration(self.duration, "duration")
        if duration < ZERO_DURATION:
            raise ValueError("business duration must be non-negative")
        object.__setattr__(self, "start", start)


@immutable_dataclass
class CadenceRule(ImmutableValue):
    anchor: datetime
    cadence_days: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "anchor", _aware_utc(self.anchor, "anchor"))
        _positive_integer(self.cadence_days, "cadence_days")


@immutable_dataclass
class _CalendarConfiguration(ImmutableValue):
    timezone_name: str
    timezone: ZoneInfo
    weekday_indices: tuple[int, ...]
    workday_start: time
    workday_end: time
    holiday_profile: str
    holiday_version: str
    holiday_horizon_end: date
    holidays: frozenset[date]


def _weekday_indices(values: object) -> tuple[int, ...]:
    if type(values) is not tuple or not values:
        raise ValueError("working weekdays must be a non-empty ordered tuple")
    try:
        indices = tuple(WEEKDAYS.index(value) for value in values)
    except ValueError as error:
        raise ValueError("working weekday is unknown") from error
    if indices != tuple(sorted(set(indices))):
        raise ValueError("working weekdays must be unique and ordered")
    return indices


def _local_time(value: object) -> time:
    if type(value) is not str or not LOCAL_TIME_PATTERN.fullmatch(value):
        raise ValueError("local work time must use HH:MM")
    return time.fromisoformat(value)


def _identifier(value: object, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f"{label} must be a non-empty identifier")
    return value


def _holiday_dates(values: object, horizon: date) -> frozenset[date]:
    if type(values) is not tuple or any(type(day) is not date for day in values):
        raise TypeError("holidays must be a tuple of dates")
    if values != tuple(sorted(set(values))):
        raise ValueError("holidays must be unique and ordered")
    if any(day > horizon for day in values):
        raise ValueError("holiday exceeds configured horizon")
    return frozenset(values)


def _calendar_configuration(
    timezone_name: object, blueprint: object
) -> _CalendarConfiguration:
    if type(blueprint) is not CalendarBlueprint:
        raise TypeError("blueprint must be a CalendarBlueprint")
    horizon = _calendar_date(blueprint.holiday_horizon_end)
    start = _local_time(blueprint.workday_start)
    end = _local_time(blueprint.workday_end)
    if start >= end:
        raise ValueError("workday interval must be ordered")
    return _CalendarConfiguration(
        timezone_name=_identifier(timezone_name, "timezone_name"),
        timezone=resolve_iana_timezone(timezone_name),
        weekday_indices=_weekday_indices(blueprint.working_weekdays),
        workday_start=start,
        workday_end=end,
        holiday_profile=_identifier(blueprint.holiday_calendar_profile, "holiday profile"),
        holiday_version=_identifier(blueprint.holiday_calendar_version, "holiday version"),
        holiday_horizon_end=horizon,
        holidays=_holiday_dates(blueprint.holidays, horizon),
    )


def _roundtrip_candidate(naive: datetime, zone: ZoneInfo, fold: int) -> datetime | None:
    localized = naive.replace(tzinfo=zone, fold=fold)
    candidate = _convert_timezone(localized, UTC)
    roundtrip = _convert_timezone(candidate, zone)
    if roundtrip.replace(tzinfo=None) != naive or roundtrip.fold != fold:
        return None
    return candidate


def _resolve_local(zone: ZoneInfo, day: date, clock: time) -> datetime:
    naive = datetime.combine(day, clock)
    candidates = tuple(
        candidate
        for fold in (0, 1)
        if (candidate := _roundtrip_candidate(naive, zone, fold)) is not None
    )
    if not candidates:
        raise ValueError("local boundary is nonexistent")
    if len(set(candidates)) > 1:
        raise ValueError("local boundary is ambiguous")
    return candidates[0]


def _create_calendar(configuration: _CalendarConfiguration) -> "BusinessCalendar":
    calendar = object.__new__(BusinessCalendar)
    object.__setattr__(calendar, "_configuration", configuration)
    return calendar


def _intersection(left: UtcInterval, right: UtcInterval) -> timedelta:
    start = max(left.start, right.start)
    end = min(left.end, right.end)
    return max(ZERO_DURATION, end - start)


def _next_day_within_horizon(day: date, horizon_end: date) -> date:
    if day >= horizon_end:
        raise ValueError("no working instant exists within the holiday horizon")
    return day + ONE_DAY


@immutable_dataclass
class BusinessCalendar(ImmutableValue):
    _configuration: _CalendarConfiguration

    def __init__(self, *_values: object, **_named_values: object) -> None:
        raise TypeError("BusinessCalendar must be constructed with from_blueprint")

    @classmethod
    def from_blueprint(
        cls, timezone_name: str, blueprint: CalendarBlueprint
    ) -> "BusinessCalendar":
        return _create_calendar(_calendar_configuration(timezone_name, blueprint))

    def business_date(self, instant: datetime) -> date:
        normalized = _aware_utc(instant, "instant")
        return _convert_timezone(normalized, self._configuration.timezone).date()

    def working_interval(self, day: date) -> UtcInterval | None:
        resolved_day = _calendar_date(day)
        config = self._configuration
        if resolved_day > config.holiday_horizon_end:
            raise ValueError("day exceeds the holiday horizon")
        if resolved_day.weekday() not in config.weekday_indices or resolved_day in config.holidays:
            return None
        start = _resolve_local(config.timezone, resolved_day, config.workday_start)
        end = _resolve_local(config.timezone, resolved_day, config.workday_end)
        return UtcInterval(start, end)

    def business_day_end(self, day: date) -> datetime | None:
        interval = self.working_interval(day)
        return None if interval is None else interval.end

    def next_working_instant(self, instant: datetime) -> datetime:
        normalized = _aware_utc(instant, "instant")
        day = self.business_date(normalized)
        while True:
            interval = self.working_interval(day)
            if interval is not None:
                if normalized < interval.start:
                    return interval.start
                if normalized < interval.end:
                    return normalized
            day = _next_day_within_horizon(day, self._configuration.holiday_horizon_end)

    def elapsed(self, interval: UtcInterval) -> DualElapsed:
        if type(interval) is not UtcInterval:
            raise TypeError("interval must be a UtcInterval")
        calendar_elapsed = interval.end - interval.start
        if calendar_elapsed == ZERO_DURATION:
            return DualElapsed(ZERO_DURATION, ZERO_DURATION)
        business_elapsed = ZERO_DURATION
        day = self.business_date(interval.start)
        final_day = self.business_date(interval.end - DATETIME_RESOLUTION)
        while day <= final_day:
            working = self.working_interval(day)
            if working is not None:
                business_elapsed += _intersection(interval, working)
            if day == final_day:
                break
            day += ONE_DAY
        return DualElapsed(calendar_elapsed, business_elapsed)

    def add(self, request: BusinessTimeAddition) -> datetime:
        if type(request) is not BusinessTimeAddition:
            raise TypeError("request must be a BusinessTimeAddition")
        if request.duration == ZERO_DURATION:
            return request.start
        remaining = request.duration
        cursor = self.next_working_instant(request.start)
        while True:
            interval = self.working_interval(self.business_date(cursor))
            if interval is None:
                raise RuntimeError("next working instant has no working interval")
            available = interval.end - cursor
            if remaining <= available:
                return cursor + remaining
            remaining -= available
            cursor = self.next_working_instant(interval.end)

    def _local_datetime(self, instant: datetime) -> datetime:
        normalized = _aware_utc(instant, "instant")
        return _convert_timezone(normalized, self._configuration.timezone)

    def _resolve_local(self, day: date, clock: time) -> datetime:
        return _resolve_local(self._configuration.timezone, day, clock)


def cadence_boundary(calendar: BusinessCalendar, rule: CadenceRule, ordinal: int) -> datetime:
    if type(calendar) is not BusinessCalendar or type(rule) is not CadenceRule:
        raise TypeError("calendar and rule must use their exact domain types")
    position = _non_negative_integer(ordinal, "ordinal")
    if position == 0:
        return rule.anchor
    local_anchor = calendar._local_datetime(rule.anchor)
    try:
        target_day = local_anchor.date() + timedelta(days=rule.cadence_days * position)
    except OverflowError as error:
        raise ValueError(DATETIME_RANGE_ERROR) from error
    local_clock = time(
        local_anchor.hour, local_anchor.minute, local_anchor.second, local_anchor.microsecond
    )
    return calendar._resolve_local(target_day, local_clock)
