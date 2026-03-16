"""Master tick orchestrator — drives the simulation engine."""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from app.engine.issue_state_machine import IssueState, JiraWriteAction, transition_issue

logger = logging.getLogger(__name__)

TICK_HOURS = 4.0
PLANNING_DURATION_HOURS = 8.0


class SimulationState(StrEnum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"


@dataclass
class TeamTickResult:
    team_id: int
    jira_actions_count: int
    events_fired: list[str]
    error: str | None


class SimulationEngine:
    """Tick-based simulation engine coordinating all modules."""

    def __init__(
        self,
        session_factory,
        write_queue,
    ):
        self._session_factory = session_factory
        self._write_queue = write_queue
        self._state = SimulationState.STOPPED
        self._paused_teams: set[int] = set()
        self._last_successful_tick: datetime | None = None
        self._tick_count: int = 0
        self.tick_interval_minutes: int = 5
        self._rng = random.Random()

    @property
    def state(self) -> SimulationState:
        return self._state

    @property
    def paused_teams(self) -> set[int]:
        return self._paused_teams.copy()

    @property
    def last_successful_tick(self) -> datetime | None:
        return self._last_successful_tick

    @property
    def tick_count(self) -> int:
        return self._tick_count

    def start(self) -> None:
        self._state = SimulationState.RUNNING
        logger.info("Simulation engine started")

    def pause(self) -> None:
        self._state = SimulationState.PAUSED
        logger.info("Simulation engine paused")

    def resume(self) -> None:
        self._state = SimulationState.RUNNING
        logger.info("Simulation engine resumed")

    def stop(self) -> None:
        self._state = SimulationState.STOPPED
        logger.info("Simulation engine stopped")

    def pause_team(self, team_id: int) -> None:
        self._paused_teams.add(team_id)
        logger.info("Team %d paused", team_id)

    def resume_team(self, team_id: int) -> None:
        self._paused_teams.discard(team_id)
        logger.info("Team %d resumed", team_id)

    def should_tick(self) -> bool:
        return self._state == SimulationState.RUNNING

    def enqueue_actions(
        self, team_id: int, actions: list[JiraWriteAction],
    ) -> None:
        """Hand off JiraWriteActions to the write queue."""
        for action in actions:
            self._write_queue.enqueue(
                team_id=team_id,
                operation_type=action.operation_type,
                payload=action.payload,
                issue_id=action.issue_id,
            )

    def record_tick_success(self, at: datetime) -> None:
        self._last_successful_tick = at
        self._tick_count += 1

    async def tick(self) -> list[TeamTickResult]:
        """Execute one simulation tick across all active teams.

        Tick sequence:
        1. Calendar check per team
        2. Per-team loop: capacity reset, sprint phase, issue advancement,
           event rolls, detections
        3. Backlog maintenance
        4. Populate write queue
        5. Persist state snapshot
        6. Record last_successful_tick
        """
        if not self.should_tick():
            return []

        results: list[TeamTickResult] = []
        session = self._session_factory()

        try:
            from app.models.team import Team
            teams = session.query(Team).filter(Team.is_active.is_(True)).all()

            for team in teams:
                if team.id in self._paused_teams:
                    continue
                result = await self._tick_team(session, team)
                results.append(result)

            session.commit()
            self.record_tick_success(datetime.now(UTC))
        except Exception as e:
            session.rollback()
            logger.exception("Tick failed: %s", e)
            raise
        finally:
            session.close()

        return results

    async def _tick_team(self, session, team) -> TeamTickResult:
        """Process a single team within a tick.

        Steps:
        1. Calendar check — skip if outside working hours
        2. Capacity reset for all members
        3. Sprint phase check — advance phase if conditions met
        4. Issue advancement — burn touch time, progress through workflow
        5. Event rolls — fire probabilistic events
        6. Backlog maintenance — generate issues if below target
        7. Enqueue Jira actions
        """
        from app.engine.backlog import (
            TemplateContentGenerator,
            check_backlog_depth,
            generate_issues,
        )
        from app.engine.calendar import is_working_time
        from app.engine.capacity import (
            advance_touch_time,
            calculate_daily_capacity,
            consume_capacity,
        )
        from app.engine.events.base import TickContext
        from app.engine.events.registry import get_all_event_types, get_event_handler
        from app.engine.sprint_lifecycle import (
            SprintPhase,
            check_phase_advance,
            detect_carry_over_issues,
        )
        from app.models.daily_capacity_log import DailyCapacityLog
        from app.models.issue import Issue
        from app.models.member import Member
        from app.models.simulation_event_config import SimulationEventConfig
        from app.models.simulation_event_log import SimulationEventLog
        from app.models.sprint import Sprint

        jira_actions: list[JiraWriteAction] = []
        events_fired: list[str] = []
        now = datetime.now(UTC)

        try:
            holidays = _parse_holidays(team.holidays)

            # --- Step 1: Calendar check ---
            if not is_working_time(
                team.timezone, team.working_hours_start,
                team.working_hours_end, holidays,
                [0, 1, 2, 3, 4], now,
            ):
                return TeamTickResult(
                    team_id=team.id, jira_actions_count=0,
                    events_fired=[], error=None,
                )

            # --- Step 2: Capacity reset ---
            members = session.query(Member).filter_by(
                team_id=team.id, is_active=True,
            ).all()
            capacity_states = {}
            for member in members:
                cap = calculate_daily_capacity(
                    member_id=member.id,
                    daily_capacity_hours=member.daily_capacity_hours,
                    timezone_name=member.timezone or team.timezone,
                    working_hours_start=team.working_hours_start,
                    working_hours_end=team.working_hours_end,
                    holidays=holidays,
                    working_days=[0, 1, 2, 3, 4],
                    at=now,
                )
                capacity_states[member.id] = cap

            # --- Step 3: Sprint phase check ---
            current_sprint = (
                session.query(Sprint)
                .filter_by(team_id=team.id)
                .filter(Sprint.status.in_(["active", "future"]))
                .order_by(Sprint.start_date.desc())
                .first()
            )

            if current_sprint is None:
                current_sprint = _create_initial_sprint(session, team, now)

            issues = session.query(Issue).filter_by(
                team_id=team.id,
            ).all()

            backlog_issues = [i for i in issues if i.status == "backlog"]
            sprint_issues = [
                i for i in issues if i.sprint_id == current_sprint.id
            ]

            sprint_capacity = sum(
                m.daily_capacity_hours for m in members
            ) * team.sprint_length_days

            sprint_start = current_sprint.start_date
            if sprint_start.tzinfo is None:
                sprint_start = sprint_start.replace(tzinfo=UTC)
            sim_day = (now - sprint_start).days

            next_phase = check_phase_advance(
                phase=SprintPhase(current_sprint.phase),
                backlog_depth=len(backlog_issues),
                sprint_capacity=int(sprint_capacity),
                planning_hours_elapsed=sim_day * 8.0,
                planning_duration_hours=PLANNING_DURATION_HOURS,
                sprint_days_elapsed=sim_day,
                sprint_length_days=team.sprint_length_days,
                pause_before_planning=team.pause_before_planning,
            )

            if next_phase is not None:
                old_phase = current_sprint.phase
                current_sprint.phase = next_phase.value
                logger.info(
                    "Team %d sprint %s: %s -> %s",
                    team.id, current_sprint.name, old_phase, next_phase.value,
                )

                if next_phase == SprintPhase.PLANNING:
                    jira_actions.extend(
                        _handle_planning_phase(
                            session, team, current_sprint, backlog_issues,
                            sprint_capacity,
                        )
                    )
                    sprint_issues = [
                        i for i in issues if i.sprint_id == current_sprint.id
                    ]

                elif next_phase == SprintPhase.ACTIVE:
                    current_sprint.status = "active"
                    if current_sprint.jira_sprint_id:
                        jira_actions.append(JiraWriteAction(
                            operation_type="UPDATE_SPRINT",
                            payload={"sprint_id": current_sprint.jira_sprint_id},
                        ))

                elif next_phase == SprintPhase.REVIEW:
                    carry_over = detect_carry_over_issues([
                        {"id": i.id, "status": i.status}
                        for i in sprint_issues
                    ])
                    current_sprint.carried_over_points = sum(
                        (i.story_points or 0)
                        for i in sprint_issues
                        if i.id in {c["id"] for c in carry_over}
                    )
                    completed_pts = sum(
                        (i.story_points or 0)
                        for i in sprint_issues
                        if i.status in ("DONE", "Done", "done")
                    )
                    committed_pts = current_sprint.committed_points or 0
                    current_sprint.completed_points = completed_pts
                    if committed_pts > 0:
                        current_sprint.velocity = completed_pts / committed_pts

                    for ci in carry_over:
                        issue_obj = session.get(Issue, ci["id"])
                        if issue_obj:
                            issue_obj.carried_over = True

                elif next_phase == SprintPhase.RETRO:
                    jira_actions.append(JiraWriteAction(
                        operation_type="ADD_COMMENT",
                        payload={
                            "issue_key": f"{team.jira_project_key}-retro",
                            "body": (
                                f"[Simulator] Sprint {current_sprint.name} "
                                f"retro — velocity "
                                f"{current_sprint.velocity or 0:.0%}"
                            ),
                        },
                    ))

                elif next_phase == SprintPhase.BACKLOG_PREP:
                    current_sprint.status = "closed"
                    if current_sprint.jira_sprint_id:
                        jira_actions.append(JiraWriteAction(
                            operation_type="COMPLETE_SPRINT",
                            payload={
                                "sprint_id": current_sprint.jira_sprint_id,
                            },
                        ))
                    current_sprint = _create_next_sprint(
                        session, team, current_sprint, now,
                    )

            # --- Step 4: Issue advancement ---
            if current_sprint.phase == SprintPhase.ACTIVE.value:
                for issue in sprint_issues:
                    if issue.status != IssueState.IN_PROGRESS.value:
                        continue
                    if issue.current_worker_id is None:
                        continue
                    cap = capacity_states.get(issue.current_worker_id)
                    if cap is None or not cap.is_working:
                        continue

                    new_remaining, new_cap = advance_touch_time(
                        issue.touch_time_remaining_hours, cap, TICK_HOURS,
                    )
                    issue.touch_time_remaining_hours = new_remaining
                    capacity_states[issue.current_worker_id] = new_cap

                    if new_remaining <= 0:
                        new_state, actions = transition_issue(
                            IssueState(issue.status),
                            "complete_step",
                            {
                                "is_last_step": True,
                                "issue_key": issue.jira_issue_key or "",
                            },
                        )
                        issue.status = new_state.value
                        if new_state == IssueState.DONE:
                            issue.completed_at = now
                        jira_actions.extend(actions)

                # Assign unassigned queued issues to available workers
                queued_issues = [
                    i for i in sprint_issues
                    if i.status == IssueState.QUEUED_FOR_ROLE.value
                    and i.current_worker_id is None
                ]
                for issue in queued_issues:
                    worker = _find_available_worker(
                        members, capacity_states, issue,
                    )
                    if worker is None:
                        continue
                    issue.current_worker_id = worker.id
                    cap = capacity_states[worker.id]
                    capacity_states[worker.id] = consume_capacity(cap, 1.0)

                    new_state, actions = transition_issue(
                        IssueState(issue.status),
                        "start_work",
                        {
                            "worker_name": worker.name,
                            "role": worker.role,
                            "issue_key": issue.jira_issue_key or "",
                        },
                    )
                    issue.status = new_state.value
                    jira_actions.extend(actions)

            # --- Step 5: Event rolls ---
            event_configs = {
                ec.event_type: ec
                for ec in session.query(SimulationEventConfig).filter_by(
                    team_id=team.id,
                ).all()
            }

            tick_context = TickContext(
                team_id=team.id,
                sprint={
                    "id": current_sprint.id,
                    "name": current_sprint.name,
                    "phase": current_sprint.phase,
                    "sprint_number": current_sprint.sprint_number,
                    "committed_points": current_sprint.committed_points,
                    "completed_points": current_sprint.completed_points,
                    "velocity": current_sprint.velocity,
                    "goal_at_risk": current_sprint.goal_at_risk,
                },
                issues=[
                    {
                        "id": i.id,
                        "status": i.status,
                        "story_points": i.story_points,
                        "sprint_id": i.sprint_id,
                        "issue_key": i.jira_issue_key,
                        "current_worker_id": i.current_worker_id,
                        "touch_time_remaining": i.touch_time_remaining_hours,
                        "is_blocked": i.is_blocked,
                        "carried_over": i.carried_over,
                        "backlog_priority": i.backlog_priority,
                    }
                    for i in sprint_issues
                ],
                members=[
                    {
                        "id": m.id,
                        "name": m.name,
                        "role": m.role,
                        "capacity": capacity_states.get(m.id),
                        "max_wip": m.max_concurrent_wip,
                    }
                    for m in members
                ],
                capacity_states=capacity_states,
                sim_day=sim_day,
                now=now,
            )

            for event_type in get_all_event_types():
                config = event_configs.get(event_type)
                if config and not config.enabled:
                    continue
                handler = get_event_handler(event_type)
                if handler is None:
                    continue
                try:
                    outcomes = handler.evaluate(
                        tick_context, rng=self._rng,
                    )
                except Exception:
                    logger.exception(
                        "Event %s failed for team %d", event_type, team.id,
                    )
                    continue

                for outcome in outcomes:
                    events_fired.append(event_type)
                    jira_actions.extend(outcome.jira_actions)

                    if current_sprint.id:
                        log_entry = SimulationEventLog(
                            team_id=team.id,
                            sprint_id=current_sprint.id,
                            event_type=event_type,
                            occurred_at=now,
                            sim_day=sim_day,
                            payload=json.dumps(outcome.log_entry),
                        )
                        session.add(log_entry)

            # --- Step 6: Backlog maintenance ---
            deficit = check_backlog_depth(
                len(backlog_issues), team.backlog_depth_target,
            )
            if deficit > 0:
                generated = await generate_issues(
                    count=min(deficit, 5),
                    team_name=team.name,
                    content_generator=TemplateContentGenerator(rng=self._rng),
                    rng=self._rng,
                )
                for gen_issue in generated:
                    new_issue = Issue(
                        team_id=team.id,
                        issue_type=gen_issue["issue_type"],
                        summary=gen_issue["summary"],
                        description=gen_issue["description"],
                        story_points=gen_issue["story_points"],
                        status="backlog",
                        backlog_priority=len(backlog_issues) + 1,
                    )
                    session.add(new_issue)
                    session.flush()

                    jira_actions.append(JiraWriteAction(
                        operation_type="CREATE_ISSUE",
                        payload={
                            "project_key": team.jira_project_key,
                            "issue_type": gen_issue["issue_type"],
                            "summary": f"[SIM] {gen_issue['summary']}",
                            "fields": {
                                "description": {
                                    "type": "doc",
                                    "version": 1,
                                    "content": [{
                                        "type": "paragraph",
                                        "content": [{
                                            "type": "text",
                                            "text": gen_issue["description"],
                                        }],
                                    }],
                                },
                            },
                        },
                        issue_id=new_issue.id,
                    ))

            # --- Step 7: Persist capacity snapshot ---
            for member_id, cap in capacity_states.items():
                if cap.is_working:
                    session.add(DailyCapacityLog(
                        member_id=member_id,
                        date=now,
                        total_hours=cap.total_hours,
                        consumed_hours=cap.consumed_hours,
                        active_wip_count=cap.active_wip_count,
                    ))

            # --- Step 8: Enqueue Jira actions ---
            self.enqueue_actions(team.id, jira_actions)

            return TeamTickResult(
                team_id=team.id,
                jira_actions_count=len(jira_actions),
                events_fired=events_fired,
                error=None,
            )
        except Exception as e:
            logger.exception("Team %d tick failed: %s", team.id, e)
            return TeamTickResult(
                team_id=team.id,
                jira_actions_count=0,
                events_fired=events_fired,
                error=str(e),
            )


def _parse_holidays(holidays_json: str) -> list:
    """Parse holidays JSON string to list of date objects."""
    try:
        return json.loads(holidays_json) if holidays_json else []
    except (json.JSONDecodeError, TypeError):
        return []


def _create_initial_sprint(session, team, now: datetime):
    """Create the first sprint for a team."""
    from app.models.sprint import Sprint

    sprint = Sprint(
        team_id=team.id,
        name=f"{team.name} Sprint 1",
        start_date=now,
        end_date=now + timedelta(days=team.sprint_length_days),
        status="future",
        phase="BACKLOG_PREP",
        sprint_number=1,
        committed_points=0,
        completed_points=0,
    )
    session.add(sprint)
    session.flush()
    logger.info("Created initial sprint for team %d: %s", team.id, sprint.name)
    return sprint


def _create_next_sprint(session, team, prev_sprint, now: datetime):
    """Create the next sprint following the previous one."""
    from app.models.sprint import Sprint

    next_number = (prev_sprint.sprint_number or 0) + 1
    sprint = Sprint(
        team_id=team.id,
        name=f"{team.name} Sprint {next_number}",
        start_date=now,
        end_date=now + timedelta(days=team.sprint_length_days),
        status="future",
        phase="BACKLOG_PREP",
        sprint_number=next_number,
        committed_points=0,
        completed_points=0,
    )
    session.add(sprint)
    session.flush()
    logger.info(
        "Created sprint %d for team %d: %s",
        next_number, team.id, sprint.name,
    )
    return sprint


def _handle_planning_phase(
    session, team, sprint, backlog_issues, sprint_capacity,
):
    """Select issues for the sprint during planning phase."""
    from app.engine.sprint_lifecycle import select_sprint_issues

    backlog_dicts = [
        {
            "id": i.id,
            "story_points": i.story_points or 0,
            "backlog_priority": i.backlog_priority,
        }
        for i in backlog_issues
    ]
    selected = select_sprint_issues(
        backlog_dicts, team.sprint_planning_strategy, int(sprint_capacity),
    )

    actions = []
    committed = 0
    for sel in selected:
        from app.models.issue import Issue
        issue = session.get(Issue, sel["id"])
        if issue:
            issue.sprint_id = sprint.id
            issue.status = IssueState.SPRINT_COMMITTED.value
            committed += issue.story_points or 0

            if issue.jira_issue_key and sprint.jira_sprint_id:
                actions.append(JiraWriteAction(
                    operation_type="ADD_TO_SPRINT",
                    payload={
                        "sprint_id": sprint.jira_sprint_id,
                        "issue_keys": [issue.jira_issue_key],
                    },
                    issue_id=issue.id,
                ))

    sprint.committed_points = committed
    logger.info(
        "Team %d: planned %d issues (%d pts) for %s",
        team.id, len(selected), committed, sprint.name,
    )
    return actions


def _find_available_worker(members, capacity_states, issue):
    """Find a member with available capacity to work on the issue."""
    from app.engine.capacity import can_accept_work

    for member in members:
        cap = capacity_states.get(member.id)
        if cap is None:
            continue
        if can_accept_work(cap, member.max_concurrent_wip):
            return member
    return None
