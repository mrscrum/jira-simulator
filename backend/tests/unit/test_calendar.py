"""Tests for the calendar module — business days, working hours, timezones."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.engine.calendar import (
    handoff_lag_hours,
    is_working_time,
    next_working_moment,
    working_days_in_range,
    working_hours_remaining_today,
)

WEEKDAYS = [0, 1, 2, 3, 4]


class TestIsWorkingTime:
    def test_weekday_during_hours_returns_true(self):
        # Monday 2026-03-16 at 10:00 UTC
        at = datetime(2026, 3, 16, 10, 0, tzinfo=UTC)
        assert is_working_time("UTC", 9, 17, [], WEEKDAYS, at) is True

    def test_weekday_before_hours_returns_false(self):
        at = datetime(2026, 3, 16, 8, 0, tzinfo=UTC)
        assert is_working_time("UTC", 9, 17, [], WEEKDAYS, at) is False

    def test_weekday_after_hours_returns_false(self):
        at = datetime(2026, 3, 16, 17, 30, tzinfo=UTC)
        assert is_working_time("UTC", 9, 17, [], WEEKDAYS, at) is False

    def test_weekend_returns_false(self):
        # Saturday 2026-03-21
        at = datetime(2026, 3, 21, 12, 0, tzinfo=UTC)
        assert is_working_time("UTC", 9, 17, [], WEEKDAYS, at) is False

    def test_holiday_returns_false(self):
        at = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)
        holidays = [date(2026, 3, 16)]
        assert is_working_time("UTC", 9, 17, holidays, WEEKDAYS, at) is False

    def test_timezone_conversion(self):
        # 14:00 UTC = 09:00 EST — start of US working hours
        at = datetime(2026, 3, 16, 14, 0, tzinfo=UTC)
        assert (
            is_working_time(
                "America/New_York", 9, 17, [], WEEKDAYS, at
            )
            is True
        )

    def test_timezone_before_local_hours(self):
        # 12:00 UTC = 07:00 EST — before US working hours
        at = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)
        assert (
            is_working_time(
                "America/New_York", 9, 17, [], WEEKDAYS, at
            )
            is False
        )

    def test_exact_start_hour_is_working(self):
        at = datetime(2026, 3, 16, 9, 0, tzinfo=UTC)
        assert is_working_time("UTC", 9, 17, [], WEEKDAYS, at) is True

    def test_exact_end_hour_is_not_working(self):
        at = datetime(2026, 3, 16, 17, 0, tzinfo=UTC)
        assert is_working_time("UTC", 9, 17, [], WEEKDAYS, at) is False


class TestNextWorkingMoment:
    def test_during_working_hours_returns_same_time(self):
        at = datetime(2026, 3, 16, 10, 0, tzinfo=UTC)
        result = next_working_moment("UTC", 9, 17, [], WEEKDAYS, at)
        assert result == at

    def test_before_working_hours_returns_start(self):
        at = datetime(2026, 3, 16, 7, 0, tzinfo=UTC)
        result = next_working_moment("UTC", 9, 17, [], WEEKDAYS, at)
        assert result.hour == 9
        assert result.date() == date(2026, 3, 16)

    def test_after_working_hours_returns_next_day(self):
        at = datetime(2026, 3, 16, 18, 0, tzinfo=UTC)
        result = next_working_moment("UTC", 9, 17, [], WEEKDAYS, at)
        assert result.hour == 9
        assert result.date() == date(2026, 3, 17)

    def test_friday_evening_returns_monday(self):
        # Friday 2026-03-20 at 18:00
        at = datetime(2026, 3, 20, 18, 0, tzinfo=UTC)
        result = next_working_moment("UTC", 9, 17, [], WEEKDAYS, at)
        assert result.date() == date(2026, 3, 23)  # Monday
        assert result.hour == 9

    def test_saturday_returns_monday(self):
        at = datetime(2026, 3, 21, 12, 0, tzinfo=UTC)
        result = next_working_moment("UTC", 9, 17, [], WEEKDAYS, at)
        assert result.date() == date(2026, 3, 23)

    def test_holiday_skipped(self):
        holidays = [date(2026, 3, 17)]
        at = datetime(2026, 3, 16, 18, 0, tzinfo=UTC)
        result = next_working_moment("UTC", 9, 17, holidays, WEEKDAYS, at)
        assert result.date() == date(2026, 3, 18)

    def test_timezone_aware(self):
        # 22:00 UTC = 17:00 EST = end of working day
        at = datetime(2026, 3, 16, 22, 0, tzinfo=UTC)
        result = next_working_moment(
            "America/New_York", 9, 17, [], WEEKDAYS, at
        )
        ny_tz = ZoneInfo("America/New_York")
        local_result = result.astimezone(ny_tz)
        assert local_result.hour == 9
        assert local_result.date() == date(2026, 3, 17)


class TestWorkingHoursRemainingToday:
    def test_at_start_of_day(self):
        at = datetime(2026, 3, 16, 9, 0, tzinfo=UTC)
        result = working_hours_remaining_today("UTC", 9, 17, at)
        assert result == 8.0

    def test_mid_day(self):
        at = datetime(2026, 3, 16, 13, 0, tzinfo=UTC)
        result = working_hours_remaining_today("UTC", 9, 17, at)
        assert result == 4.0

    def test_after_hours_returns_zero(self):
        at = datetime(2026, 3, 16, 18, 0, tzinfo=UTC)
        result = working_hours_remaining_today("UTC", 9, 17, at)
        assert result == 0.0

    def test_before_hours_returns_full_day(self):
        at = datetime(2026, 3, 16, 7, 0, tzinfo=UTC)
        result = working_hours_remaining_today("UTC", 9, 17, at)
        assert result == 8.0

    def test_half_hour_precision(self):
        at = datetime(2026, 3, 16, 15, 30, tzinfo=UTC)
        result = working_hours_remaining_today("UTC", 9, 17, at)
        assert result == 1.5


class TestWorkingDaysInRange:
    def test_full_week(self):
        start = date(2026, 3, 16)  # Monday
        end = date(2026, 3, 20)  # Friday
        result = working_days_in_range(
            "UTC", 9, 17, [], WEEKDAYS, start, end
        )
        assert result == 5

    def test_includes_weekend(self):
        start = date(2026, 3, 16)  # Monday
        end = date(2026, 3, 22)  # Sunday
        result = working_days_in_range(
            "UTC", 9, 17, [], WEEKDAYS, start, end
        )
        assert result == 5

    def test_two_weeks(self):
        start = date(2026, 3, 16)
        end = date(2026, 3, 29)
        result = working_days_in_range(
            "UTC", 9, 17, [], WEEKDAYS, start, end
        )
        assert result == 10

    def test_holiday_excluded(self):
        start = date(2026, 3, 16)
        end = date(2026, 3, 20)
        holidays = [date(2026, 3, 18)]
        result = working_days_in_range(
            "UTC", 9, 17, holidays, WEEKDAYS, start, end
        )
        assert result == 4

    def test_same_day(self):
        d = date(2026, 3, 16)
        result = working_days_in_range("UTC", 9, 17, [], WEEKDAYS, d, d)
        assert result == 1

    def test_weekend_only(self):
        start = date(2026, 3, 21)  # Saturday
        end = date(2026, 3, 22)  # Sunday
        result = working_days_in_range(
            "UTC", 9, 17, [], WEEKDAYS, start, end
        )
        assert result == 0


class TestHandoffLagHours:
    def test_both_working_zero_lag(self):
        # 15:00 UTC, London (15:00) hands off to NYC (10:00 EST)
        at = datetime(2026, 3, 16, 15, 0, tzinfo=UTC)
        result = handoff_lag_hours(
            "Europe/London", 17,
            "America/New_York", 9, [],
            WEEKDAYS, at,
        )
        assert result == 0.0

    def test_nyc_to_london_overnight_lag(self):
        # 22:00 UTC = 17:00 EST (NYC done) → London next day 09:00 GMT
        at = datetime(2026, 3, 16, 22, 0, tzinfo=UTC)
        result = handoff_lag_hours(
            "America/New_York", 17,
            "Europe/London", 9, [],
            WEEKDAYS, at,
        )
        assert result == 11.0  # 22:00 to 09:00 next day

    def test_friday_to_monday_lag(self):
        # Friday 22:00 UTC → London Monday 09:00
        at = datetime(2026, 3, 20, 22, 0, tzinfo=UTC)
        result = handoff_lag_hours(
            "America/New_York", 17,
            "Europe/London", 9, [],
            WEEKDAYS, at,
        )
        # 22:00 Friday to 09:00 Monday = 59 hours
        assert result == 59.0
