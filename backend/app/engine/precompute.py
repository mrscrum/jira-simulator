"""Pre-compute an entire sprint's events in-memory.

Runs the same simulation logic (workflow_engine, capacity, sprint_lifecycle,
calendar) on snapshot dataclasses, producing a list of timestamped
ScheduledEvent records without touching the database.
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from app.engine.calendar import next_working_moment
from app.engine.capacity import build_member_states
from app.engine.snapshots import (
    IssueSnapshot,
    MemberSnapshot,
    TeamSnapshot,
)
from app.engine.sprint_lifecycle import check_sprint_end, plan_sprint
from app.engine.types import JiraWriteAction
from app.engine.workflow_engine import enter_status, get_touch_time_config, process_item_tick

logger = logging.getLogger(__name__)

DEFAULT_WORKING_DAYS = [0, 1, 2, 3, 4]  # Monday-Friday


@dataclass
class ScheduledEventData:
    """One event produced by pre-computation."""

    sim_tick: int
    wall_clock_time: datetime
    event_type: str
    payload: dict
    issue_id: int | None
    sequence_order: int


@dataclass
class PrecomputeResult:
    """Output of a sprint pre-computation."""

    events: list[ScheduledEventData]
    total_ticks: int
    rng_seed: int
    issue_final_states: dict[int, IssueSnapshot]
    committed_points: int
    selected_issue_ids: list[int]
    capacity_target: int


def _parse_holidays(holidays_json: str) -> list[date]:
    """Parse holidays JSON string into list of date objects."""
    try:
        raw = json.loads(holidays_json) if holidays_json else []
    except (json.JSONDecodeError, TypeError):
        raw = []
    result = []
    for h in raw:
        if isinstance(h, str):
            try:
                result.append(date.fromisoformat(h))
            except ValueError:
                pass
    return result


def _compute_tick_wall_times(
    sprint_start: datetime,
    sprint_length_days: int,
    tick_duration_hours: float,
    tz_name: str,
    start_hour: int,
    end_hour: int,
    holidays: list[date],
    working_days: list[int],
) -> list[datetime]:
    """Compute wall-clock timestamps for each tick in the sprint.

    Advances from sprint_start by tick_duration_hours, skipping
    non-working time via next_working_moment().
    """
    sprint_end = sprint_start + timedelta(days=sprint_length_days)
    tick_delta = timedelta(hours=tick_duration_hours)

    tick_times: list[datetime] = []
    current = sprint_start

    # Ensure starting in working time
    current = next_working_moment(
        tz_name, start_hour, end_hour, holidays, working_days, current,
    )

    while current < sprint_end:
        tick_times.append(current)
        current = current + tick_delta
        # Snap to next working moment if we drifted outside
        current = next_working_moment(
            tz_name, start_hour, end_hour, holidays, working_days, current,
        )

    return tick_times


def precompute_sprint(
    team: TeamSnapshot,
    backlog_issues: list[IssueSnapshot],
    workflow_steps: list,
    touch_time_configs: dict[tuple[int, str, int], object],
    move_left_configs: list,
    members: list[MemberSnapshot],
    sprint_start: datetime,
    sprint_length_days: int,
    jira_sprint_id: int | None = None,
    jira_board_id: int | None = None,
    sprint_name: str = "Sprint",
    sprint_db_id: int | None = None,
    rng_seed: int | None = None,
) -> PrecomputeResult:
    """Run the full sprint simulation in-memory, returning timestamped events.

    Uses the same pure functions as the tick engine:
    - plan_sprint() for backlog selection
    - enter_status() for status transitions
    - process_item_tick() for per-item per-tick processing
    - check_sprint_end() for sprint completion

    Args:
        team: team configuration snapshot
        backlog_issues: prioritized backlog (carryover first)
        workflow_steps: ordered workflow step objects (snapshot or ORM)
        touch_time_configs: keyed by (step_id, issue_type, story_points)
        move_left_configs: list of MoveLeftConfig objects with .targets
        members: active team members
        sprint_start: when the sprint begins (UTC)
        sprint_length_days: sprint duration in calendar days
        jira_sprint_id: Jira sprint ID (if known from bootstrap)
        jira_board_id: Jira board ID for CREATE_SPRINT
        sprint_name: name for the sprint
        sprint_db_id: DB id of the sprint record
        rng_seed: seed for deterministic results (auto-generated if None)

    Returns:
        PrecomputeResult with all scheduled events and final issue states
    """
    if rng_seed is None:
        rng_seed = random.randint(0, 2**31 - 1)
    rng = random.Random(rng_seed)

    holidays = _parse_holidays(team.holidays)
    working_days = DEFAULT_WORKING_DAYS
    tick_hours = team.tick_duration_hours or 1.0

    events: list[ScheduledEventData] = []
    seq = 0  # global sequence counter

    def _add_event(
        tick: int,
        wall_time: datetime,
        action: JiraWriteAction,
    ) -> None:
        nonlocal seq
        events.append(ScheduledEventData(
            sim_tick=tick,
            wall_clock_time=wall_time,
            event_type=action.operation_type,
            payload=action.payload,
            issue_id=action.issue_id,
            sequence_order=seq,
        ))
        seq += 1

    # Compute tick schedule
    tick_times = _compute_tick_wall_times(
        sprint_start, sprint_length_days, tick_hours,
        team.timezone, team.working_hours_start, team.working_hours_end,
        holidays, working_days,
    )

    if not tick_times:
        return PrecomputeResult(
            events=[],
            total_ticks=0,
            rng_seed=rng_seed,
            issue_final_states={},
            committed_points=0,
            selected_issue_ids=[],
            capacity_target=0,
        )

    if not workflow_steps:
        return PrecomputeResult(
            events=[],
            total_ticks=0,
            rng_seed=rng_seed,
            issue_final_states={},
            committed_points=0,
            selected_issue_ids=[],
            capacity_target=0,
        )

    final_step = workflow_steps[-1]
    planning_time = tick_times[0]

    # ── Tick 0: Planning ──────────────────────────────────────────────────

    # CREATE_SPRINT event
    if jira_board_id:
        sprint_end = sprint_start + timedelta(days=sprint_length_days)
        _add_event(0, planning_time, JiraWriteAction(
            operation_type="CREATE_SPRINT",
            payload={
                "board_id": jira_board_id,
                "name": sprint_name,
                "start_date": sprint_start.isoformat(),
                "end_date": sprint_end.isoformat(),
                "_sprint_db_id": sprint_db_id,
            },
        ))

    # Select issues for sprint
    backlog_dicts = [
        {
            "id": i.id,
            "story_points": i.story_points or 0,
            "backlog_priority": i.backlog_priority,
        }
        for i in backlog_issues
    ]
    selected, capacity_target = plan_sprint(
        backlog_dicts, team.sprint_capacity_min,
        team.sprint_capacity_max, team.priority_randomization, rng,
    )

    # Build lookup from backlog_issues by id
    issue_map: dict[int, IssueSnapshot] = {i.id: i for i in backlog_issues}
    sprint_issues: list[IssueSnapshot] = []
    committed_points = 0

    for sel in selected:
        issue = issue_map.get(sel["id"])
        if issue is None:
            continue
        issue.sprint_id = sprint_db_id
        sprint_issues.append(issue)
        committed_points += issue.story_points or 0

        # Enter first workflow step
        first_step = workflow_steps[0]
        ttc = get_touch_time_config(
            touch_time_configs, first_step.id,
            issue.issue_type, issue.story_points or 0,
        )
        actions = enter_status(issue, first_step, ttc, rng)
        for action in actions:
            _add_event(0, planning_time, action)

        # ADD_TO_SPRINT event
        if issue.jira_issue_key and jira_sprint_id:
            _add_event(0, planning_time, JiraWriteAction(
                operation_type="ADD_TO_SPRINT",
                payload={
                    "sprint_id": jira_sprint_id,
                    "issue_keys": [issue.jira_issue_key],
                },
                issue_id=issue.id,
            ))

    # Start sprint in Jira
    if jira_sprint_id:
        _add_event(0, planning_time, JiraWriteAction(
            operation_type="UPDATE_SPRINT",
            payload={"sprint_id": jira_sprint_id},
        ))

    # ── Ticks 1..N: Active phase ─────────────────────────────────────────

    completed_points = 0

    for tick_idx, wall_time in enumerate(tick_times[1:], start=1):
        # Build fresh member states each tick (no sticky across ticks in snapshot)
        member_dicts = [
            {"id": m.id, "role": m.role, "assigned_issue_id": None}
            for m in members
        ]
        member_states = build_member_states(member_dicts)

        for issue in sprint_issues:
            if issue.completed_at is not None:
                continue

            result = process_item_tick(
                issue, workflow_steps, touch_time_configs,
                move_left_configs, member_states, tick_hours, rng,
            )

            for action in result.jira_actions:
                _add_event(tick_idx, wall_time, action)

            member_states = result.member_states

            if result.completed:
                issue.completed_at = wall_time
                issue.status = final_step.jira_status
                completed_points += issue.story_points or 0

        # Check sprint end
        sprint_start_utc = sprint_start
        if sprint_start_utc.tzinfo is None:
            sprint_start_utc = sprint_start_utc.replace(tzinfo=UTC)
        if check_sprint_end(sprint_start_utc, sprint_length_days, wall_time):
            if jira_sprint_id:
                _add_event(tick_idx, wall_time, JiraWriteAction(
                    operation_type="COMPLETE_SPRINT",
                    payload={"sprint_id": jira_sprint_id},
                ))
            break

    # ── Build final states ────────────────────────────────────────────────

    issue_final_states = {i.id: i for i in sprint_issues}
    total_ticks = len(tick_times)

    logger.info(
        "Pre-computed sprint '%s': %d events across %d ticks (seed=%d)",
        sprint_name, len(events), total_ticks, rng_seed,
    )

    return PrecomputeResult(
        events=events,
        total_ticks=total_ticks,
        rng_seed=rng_seed,
        issue_final_states=issue_final_states,
        committed_points=committed_points,
        selected_issue_ids=[i.id for i in sprint_issues],
        capacity_target=capacity_target,
    )
