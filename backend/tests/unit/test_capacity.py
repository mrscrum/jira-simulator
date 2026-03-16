"""Tests for the capacity module — WIP, hours, touch-time advancement."""

from datetime import UTC, date, datetime

from app.engine.capacity import (
    DailyCapacityState,
    advance_touch_time,
    calculate_daily_capacity,
    can_accept_work,
    consume_capacity,
    get_available_workers,
)


def _make_capacity(
    member_id: int = 1,
    total_hours: float = 6.0,
    consumed_hours: float = 0.0,
    active_wip_count: int = 0,
    is_working: bool = True,
) -> DailyCapacityState:
    return DailyCapacityState(
        member_id=member_id,
        date=date(2026, 3, 16),
        total_hours=total_hours,
        consumed_hours=consumed_hours,
        available_hours=total_hours - consumed_hours,
        active_wip_count=active_wip_count,
        is_working=is_working,
    )


class TestCanAcceptWork:
    def test_has_hours_and_wip_room_returns_true(self):
        cap = _make_capacity(total_hours=6.0, consumed_hours=2.0, active_wip_count=1)
        assert can_accept_work(cap, max_wip=3, wip_contribution=1.0) is True

    def test_no_available_hours_returns_false(self):
        cap = _make_capacity(total_hours=6.0, consumed_hours=6.0, active_wip_count=0)
        assert can_accept_work(cap, max_wip=3, wip_contribution=1.0) is False

    def test_at_wip_ceiling_returns_false(self):
        cap = _make_capacity(total_hours=6.0, consumed_hours=0.0, active_wip_count=3)
        assert can_accept_work(cap, max_wip=3, wip_contribution=1.0) is False

    def test_not_working_returns_false(self):
        cap = _make_capacity(is_working=False)
        assert can_accept_work(cap, max_wip=3, wip_contribution=1.0) is False

    def test_fractional_wip_contribution(self):
        cap = _make_capacity(active_wip_count=2)
        assert can_accept_work(cap, max_wip=3, wip_contribution=0.5) is True


class TestConsumeCapacity:
    def test_consumes_hours(self):
        cap = _make_capacity(total_hours=6.0, consumed_hours=0.0)
        result = consume_capacity(cap, hours=2.0, wip_contribution=1.0)
        assert result.consumed_hours == 2.0
        assert result.available_hours == 4.0
        assert result.active_wip_count == 1

    def test_does_not_exceed_total(self):
        cap = _make_capacity(total_hours=6.0, consumed_hours=5.0)
        result = consume_capacity(cap, hours=3.0, wip_contribution=1.0)
        assert result.consumed_hours == 6.0
        assert result.available_hours == 0.0


class TestAdvanceTouchTime:
    def test_burns_down_touch_time(self):
        cap = _make_capacity(total_hours=6.0, consumed_hours=0.0)
        remaining, updated_cap = advance_touch_time(
            touch_time_remaining=4.0,
            capacity=cap,
            tick_hours=2.0,
        )
        assert remaining == 2.0
        assert updated_cap.consumed_hours == 2.0

    def test_caps_at_available_hours(self):
        cap = _make_capacity(total_hours=6.0, consumed_hours=5.0)
        remaining, updated_cap = advance_touch_time(
            touch_time_remaining=4.0,
            capacity=cap,
            tick_hours=2.0,
        )
        assert remaining == 3.0  # only 1 hour available
        assert updated_cap.consumed_hours == 6.0

    def test_completes_touch_time(self):
        cap = _make_capacity(total_hours=6.0, consumed_hours=0.0)
        remaining, updated_cap = advance_touch_time(
            touch_time_remaining=1.0,
            capacity=cap,
            tick_hours=2.0,
        )
        assert remaining == 0.0
        assert updated_cap.consumed_hours == 1.0

    def test_zero_remaining_no_change(self):
        cap = _make_capacity(total_hours=6.0, consumed_hours=0.0)
        remaining, updated_cap = advance_touch_time(
            touch_time_remaining=0.0,
            capacity=cap,
            tick_hours=2.0,
        )
        assert remaining == 0.0
        assert updated_cap.consumed_hours == 0.0


class TestCalculateDailyCapacity:
    def test_working_day(self):
        at = datetime(2026, 3, 16, 10, 0, tzinfo=UTC)
        cap = calculate_daily_capacity(
            member_id=1,
            daily_capacity_hours=6.0,
            timezone_name="UTC",
            working_hours_start=9,
            working_hours_end=17,
            holidays=[],
            working_days=[0, 1, 2, 3, 4],
            at=at,
        )
        assert cap.is_working is True
        assert cap.total_hours == 6.0
        assert cap.consumed_hours == 0.0
        assert cap.available_hours == 6.0

    def test_weekend_not_working(self):
        at = datetime(2026, 3, 21, 10, 0, tzinfo=UTC)  # Saturday
        cap = calculate_daily_capacity(
            member_id=1,
            daily_capacity_hours=6.0,
            timezone_name="UTC",
            working_hours_start=9,
            working_hours_end=17,
            holidays=[],
            working_days=[0, 1, 2, 3, 4],
            at=at,
        )
        assert cap.is_working is False
        assert cap.total_hours == 0.0

    def test_holiday_not_working(self):
        at = datetime(2026, 3, 16, 10, 0, tzinfo=UTC)
        cap = calculate_daily_capacity(
            member_id=1,
            daily_capacity_hours=6.0,
            timezone_name="UTC",
            working_hours_start=9,
            working_hours_end=17,
            holidays=[date(2026, 3, 16)],
            working_days=[0, 1, 2, 3, 4],
            at=at,
        )
        assert cap.is_working is False
        assert cap.total_hours == 0.0


class TestGetAvailableWorkers:
    def test_filters_by_role(self):
        members = [
            {"id": 1, "role": "DEV", "capacity": _make_capacity(member_id=1)},
            {"id": 2, "role": "QA", "capacity": _make_capacity(member_id=2)},
            {"id": 3, "role": "DEV", "capacity": _make_capacity(member_id=3)},
        ]
        result = get_available_workers(members, "DEV", max_wip=3)
        assert len(result) == 2
        assert all(m["role"] == "DEV" for m in result)

    def test_excludes_at_wip_ceiling(self):
        members = [
            {
                "id": 1,
                "role": "DEV",
                "capacity": _make_capacity(member_id=1, active_wip_count=3),
            },
            {
                "id": 2,
                "role": "DEV",
                "capacity": _make_capacity(member_id=2, active_wip_count=0),
            },
        ]
        result = get_available_workers(members, "DEV", max_wip=3)
        assert len(result) == 1
        assert result[0]["id"] == 2

    def test_excludes_not_working(self):
        members = [
            {
                "id": 1,
                "role": "DEV",
                "capacity": _make_capacity(member_id=1, is_working=False),
            },
        ]
        result = get_available_workers(members, "DEV", max_wip=3)
        assert len(result) == 0
