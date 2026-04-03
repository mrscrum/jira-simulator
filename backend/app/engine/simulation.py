"""Master tick orchestrator — drives the simulation engine.

Rewritten to delegate to:
- workflow_engine (per-item tick processing)
- capacity (member tick states)
- sprint_lifecycle (planning, carryover, sprint end)
- calendar (working time check)
- backlog (backlog depth maintenance)
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from app.engine.sim_clock import SimClock
from app.engine.types import JiraWriteAction

logger = logging.getLogger(__name__)


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
        sim_clock: SimClock | None = None,
    ):
        self._session_factory = session_factory
        self._write_queue = write_queue
        self._clock = sim_clock or SimClock(speed_multiplier=1.0)
        self._state = SimulationState.STOPPED
        self._paused_teams: set[int] = set()
        self._last_successful_tick: datetime | None = None
        self._tick_count: int = 0
        self.tick_interval_minutes: int = 5
        self._rng = random.Random()

    @property
    def clock(self) -> SimClock:
        return self._clock

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
        session=None,
    ) -> None:
        """Hand off JiraWriteActions to the write queue."""
        for action in actions:
            self._write_queue.enqueue(
                team_id=team_id,
                operation_type=action.operation_type,
                payload=action.payload,
                issue_id=action.issue_id,
                session=session,
            )

    def record_tick_success(self, at: datetime) -> None:
        self._last_successful_tick = at
        self._tick_count += 1

    async def compute_and_schedule_sprint(
        self, team_id: int, rng_seed: int | None = None,
    ) -> dict:
        """Pre-compute a full sprint and store events as a schedule.

        1. Load team, workflow, members, backlog, configs from DB.
        2. Create sprint record.
        3. Run precompute_sprint() in-memory on snapshots.
        4. Bulk-insert ScheduledEvent rows.
        5. Create PrecomputationRun record.
        6. Apply planning results (sprint_id on issues, committed_points).

        Returns:
            dict with batch_id, total_events, total_ticks, sprint_id.
        """
        from uuid import uuid4

        from app.engine.precompute import precompute_sprint
        from app.engine.snapshots import (
            issue_to_snapshot,
            member_to_snapshot,
            move_left_config_to_snapshot,
            team_to_snapshot,
            touch_time_config_to_snapshot,
            workflow_step_to_snapshot,
        )
        from app.models.issue import Issue
        from app.models.member import Member
        from app.models.move_left_config import MoveLeftConfig
        from app.models.precomputation_run import PrecomputationRun
        from app.models.scheduled_event import ScheduledEvent
        from app.models.team import Team
        from app.models.touch_time_config import TouchTimeConfig
        from app.models.workflow import Workflow
        from app.models.workflow_step import WorkflowStep

        session = self._session_factory()
        try:
            team = session.get(Team, team_id)
            if team is None:
                raise ValueError(f"Team {team_id} not found")

            # Load workflow
            workflow = session.query(Workflow).filter_by(team_id=team.id).first()
            if workflow is None:
                raise ValueError(f"No workflow configured for team {team_id}")

            workflow_steps = (
                session.query(WorkflowStep)
                .filter_by(workflow_id=workflow.id)
                .order_by(WorkflowStep.order)
                .all()
            )
            if not workflow_steps:
                raise ValueError(f"No workflow steps for team {team_id}")

            final_step = workflow_steps[-1]

            # Load members
            members = (
                session.query(Member)
                .filter_by(team_id=team.id, is_active=True)
                .all()
            )

            # Load touch time configs
            step_ids = [s.id for s in workflow_steps]
            all_ttcs = (
                session.query(TouchTimeConfig)
                .filter(TouchTimeConfig.workflow_step_id.in_(step_ids))
                .all()
            )

            # Load move-left configs
            move_left_configs = (
                session.query(MoveLeftConfig)
                .filter_by(team_id=team.id)
                .all()
            )

            # Load backlog
            backlog_issues = (
                session.query(Issue)
                .filter_by(team_id=team.id)
                .filter(
                    Issue.sprint_id.is_(None),
                    Issue.completed_at.is_(None),
                    Issue.issue_type != "Epic",
                    Issue.status != final_step.jira_status,
                )
                .order_by(
                    Issue.carried_over.desc(),
                    Issue.backlog_priority.asc(),
                )
                .all()
            )

            # Create sprint record
            now = datetime.now(UTC)
            sprint = _create_next_sprint(session, team, now)

            # Build snapshots
            team_snap = team_to_snapshot(team)
            member_snaps = [member_to_snapshot(m) for m in members]
            issue_snaps = [issue_to_snapshot(i) for i in backlog_issues]
            step_snaps = [workflow_step_to_snapshot(s) for s in workflow_steps]
            ttc_snaps = {
                (t.workflow_step_id, t.issue_type, t.story_points): touch_time_config_to_snapshot(t)
                for t in all_ttcs
            }
            ml_snaps = [move_left_config_to_snapshot(c) for c in move_left_configs]

            # Run pre-computation
            result = precompute_sprint(
                team=team_snap,
                backlog_issues=issue_snaps,
                workflow_steps=step_snaps,
                touch_time_configs=ttc_snaps,
                move_left_configs=ml_snaps,
                members=member_snaps,
                sprint_start=sprint.start_date,
                sprint_length_days=team.sprint_length_days,
                jira_sprint_id=sprint.jira_sprint_id,
                jira_board_id=team.jira_board_id,
                sprint_name=sprint.name,
                sprint_db_id=sprint.id,
                rng_seed=rng_seed,
            )

            # Bulk-insert scheduled events
            batch_id = str(uuid4())
            for event_data in result.events:
                sched_event = ScheduledEvent(
                    team_id=team.id,
                    sprint_id=sprint.id,
                    issue_id=event_data.issue_id,
                    event_type=event_data.event_type,
                    scheduled_at=event_data.wall_clock_time,
                    sim_tick=event_data.sim_tick,
                    payload=event_data.payload,
                    status="PENDING",
                    batch_id=batch_id,
                    sequence_order=event_data.sequence_order,
                )
                session.add(sched_event)

            # Create precomputation run record
            run = PrecomputationRun(
                batch_id=batch_id,
                team_id=team.id,
                sprint_id=sprint.id,
                rng_seed=result.rng_seed,
                total_events=len(result.events),
                total_ticks=result.total_ticks,
            )
            session.add(run)

            # Apply planning results to DB
            for issue_id in result.selected_issue_ids:
                issue = session.get(Issue, issue_id)
                if issue:
                    issue.sprint_id = sprint.id

            sprint.committed_points = result.committed_points
            sprint.capacity_target = result.capacity_target
            sprint.phase = "ACTIVE"
            sprint.status = "active"

            session.commit()

            logger.info(
                "Pre-computed sprint %d for team %d: %d events, batch=%s",
                sprint.id, team.id, len(result.events), batch_id,
            )

            return {
                "batch_id": batch_id,
                "total_events": len(result.events),
                "total_ticks": result.total_ticks,
                "sprint_id": sprint.id,
            }

        except Exception:
            session.rollback()
            logger.exception("Sprint precomputation failed for team %d", team_id)
            raise
        finally:
            session.close()

    async def tick(self) -> list[TeamTickResult]:
        """Execute one simulation tick across all active teams."""
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
            self.record_tick_success(self._clock.now())
        except Exception as e:
            session.rollback()
            logger.exception("Tick failed: %s", e)
            raise
        finally:
            session.close()

        return results

    async def _tick_team(self, session, team) -> TeamTickResult:
        """Process a single team within a tick.

        Simplified flow:
        1. Calendar check — skip if outside working hours
        2. Build member tick states
        3. Sprint phase dispatch (PLANNING → ACTIVE → COMPLETED)
        4. Process active sprint items via workflow engine
        5. Backlog maintenance
        6. Enqueue Jira actions
        """
        from app.engine.backlog import (
            TemplateContentGenerator,
            check_backlog_depth,
            generate_issues,
        )
        from app.engine.calendar import is_working_time
        from app.engine.capacity import build_member_states
        from app.engine.sprint_lifecycle import (
            SprintPhase,
            calculate_velocity,
            check_sprint_end,
            handle_carryover,
            plan_sprint,
        )
        from app.engine.workflow_engine import (
            enter_status,
            get_touch_time_config,
            process_item_tick,
        )
        from app.models.issue import Issue
        from app.models.member import Member
        from app.models.move_left_config import MoveLeftConfig
        from app.models.touch_time_config import TouchTimeConfig
        from app.models.workflow import Workflow
        from app.models.workflow_step import WorkflowStep

        jira_actions: list[JiraWriteAction] = []
        now = self._clock.now()
        tick_hours = team.tick_duration_hours or 1.0

        story_points_field_id = _get_config_value(session, "field_id_story_points")
        _get_config_value(session, "field_id_sim_assignee")
        sim_reporter_field_id = _get_config_value(session, "field_id_sim_reporter")

        try:
            holidays = _parse_holidays(team.holidays)

            # --- Step 1: Calendar check ---
            if self._clock.speed <= 1.0 and not is_working_time(
                team.timezone, team.working_hours_start,
                team.working_hours_end, holidays,
                [0, 1, 2, 3, 4], now,
            ):
                return TeamTickResult(
                    team_id=team.id, jira_actions_count=0,
                    events_fired=[], error=None,
                )

            # --- Step 2: Build member tick states ---
            members = session.query(Member).filter_by(
                team_id=team.id, is_active=True,
            ).all()
            member_dicts = [
                {"id": m.id, "role": m.role, "assigned_issue_id": None}
                for m in members
            ]
            member_states = build_member_states(member_dicts)

            # --- Load team workflow ---
            workflow = session.query(Workflow).filter_by(team_id=team.id).first()
            if workflow is None:
                return TeamTickResult(
                    team_id=team.id, jira_actions_count=0,
                    events_fired=[], error="No workflow configured",
                )

            workflow_steps = (
                session.query(WorkflowStep)
                .filter_by(workflow_id=workflow.id)
                .order_by(WorkflowStep.order)
                .all()
            )
            if not workflow_steps:
                return TeamTickResult(
                    team_id=team.id, jira_actions_count=0,
                    events_fired=[], error="No workflow steps configured",
                )

            final_step = workflow_steps[-1]

            # --- Load touch time configs (keyed by step_id, issue_type, story_points) ---
            step_ids = [s.id for s in workflow_steps]
            all_ttcs = (
                session.query(TouchTimeConfig)
                .filter(TouchTimeConfig.workflow_step_id.in_(step_ids))
                .all()
            )
            touch_time_configs = {
                (t.workflow_step_id, t.issue_type, t.story_points): t
                for t in all_ttcs
            }

            # --- Load move-left configs ---
            move_left_configs = (
                session.query(MoveLeftConfig)
                .filter_by(team_id=team.id)
                .all()
            )

            # --- Step 3: Get or create sprint ---
            sprint = _get_active_or_planning_sprint(session, team.id)

            # Handle completed sprint → carryover + new sprint
            if sprint is not None and sprint.phase == SprintPhase.COMPLETED.value:
                # Carryover incomplete items
                incomplete = [
                    i for i in sprint.issues
                    if i.completed_at is None and i.status != final_step.jira_status
                ]
                if incomplete:
                    carryover_dicts = [
                        {
                            "id": i.id,
                            "sampled_work_time": i.sampled_work_time,
                            "elapsed_work_time": i.elapsed_work_time,
                            "sampled_full_time": i.sampled_full_time,
                            "elapsed_full_time": i.elapsed_full_time,
                            "work_started": i.work_started,
                            "current_worker_id": i.current_worker_id,
                            "carried_over": i.carried_over,
                        }
                        for i in incomplete
                    ]
                    handle_carryover(carryover_dicts)
                    # Apply back to ORM objects
                    for cd in carryover_dicts:
                        issue_obj = session.get(Issue, cd["id"])
                        if issue_obj:
                            issue_obj.sampled_work_time = cd["sampled_work_time"]
                            issue_obj.sampled_full_time = cd["sampled_full_time"]
                            issue_obj.work_started = cd["work_started"]
                            issue_obj.current_worker_id = cd["current_worker_id"]
                            issue_obj.carried_over = True
                            issue_obj.sprint_id = None  # will be re-assigned in planning

                # Calculate velocity for completed sprint
                completed_pts = sprint.completed_points or 0
                committed_pts = sprint.committed_points or 0
                sprint.velocity = calculate_velocity(completed_pts, committed_pts)

                sprint = None  # trigger new sprint creation below

            if sprint is None:
                sprint = _create_next_sprint(session, team, now)
                if team.jira_board_id:
                    jira_actions.append(JiraWriteAction(
                        operation_type="CREATE_SPRINT",
                        payload={
                            "board_id": team.jira_board_id,
                            "name": sprint.name,
                            "start_date": now.isoformat(),
                            "end_date": sprint.end_date.isoformat(),
                            "_sprint_db_id": sprint.id,
                        },
                    ))

            # --- Phase dispatch ---
            if sprint.phase == SprintPhase.PLANNING.value:
                # Get prioritized backlog (carryover items + regular backlog)
                backlog_issues = _get_prioritized_backlog(session, team.id, final_step.jira_status)

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
                    team.sprint_capacity_max, team.priority_randomization,
                    self._rng,
                )

                sprint.capacity_target = capacity_target
                committed = 0
                for sel in selected:
                    issue = session.get(Issue, sel["id"])
                    if issue is None:
                        continue
                    issue.sprint_id = sprint.id
                    committed += issue.story_points or 0

                    # Enter first workflow step
                    first_step = workflow_steps[0]
                    ttc = get_touch_time_config(
                        touch_time_configs, first_step.id,
                        issue.issue_type, issue.story_points or 0,
                    )
                    actions = enter_status(issue, first_step, ttc, self._rng)
                    jira_actions.extend(actions)

                    # Add to sprint in Jira
                    if issue.jira_issue_key and sprint.jira_sprint_id:
                        jira_actions.append(JiraWriteAction(
                            operation_type="ADD_TO_SPRINT",
                            payload={
                                "sprint_id": sprint.jira_sprint_id,
                                "issue_keys": [issue.jira_issue_key],
                            },
                            issue_id=issue.id,
                        ))

                sprint.committed_points = committed
                sprint.phase = SprintPhase.ACTIVE.value
                sprint.status = "active"

                # Start sprint in Jira
                if sprint.jira_sprint_id:
                    jira_actions.append(JiraWriteAction(
                        operation_type="UPDATE_SPRINT",
                        payload={"sprint_id": sprint.jira_sprint_id},
                    ))

                logger.info(
                    "Team %d: planned %d issues (%d pts) for %s",
                    team.id, len(selected), committed, sprint.name,
                )

            elif sprint.phase == SprintPhase.ACTIVE.value:
                # Process each item in the sprint
                sprint_issues = (
                    session.query(Issue)
                    .filter_by(sprint_id=sprint.id)
                    .all()
                )

                for issue in sprint_issues:
                    if issue.completed_at is not None:
                        continue

                    result = process_item_tick(
                        issue, workflow_steps, touch_time_configs,
                        move_left_configs, member_states, tick_hours, self._rng,
                    )
                    jira_actions.extend(result.jira_actions)
                    member_states = result.member_states

                    if result.completed:
                        issue.completed_at = now
                        issue.status = final_step.jira_status
                        sprint.completed_points = (
                            (sprint.completed_points or 0) + (issue.story_points or 0)
                        )

                # Check sprint end
                sprint_start = sprint.start_date
                if sprint_start.tzinfo is None:
                    sprint_start = sprint_start.replace(tzinfo=UTC)
                if check_sprint_end(sprint_start, team.sprint_length_days, now):
                    sprint.phase = SprintPhase.COMPLETED.value
                    sprint.status = "closed"
                    if sprint.jira_sprint_id:
                        jira_actions.append(JiraWriteAction(
                            operation_type="COMPLETE_SPRINT",
                            payload={"sprint_id": sprint.jira_sprint_id},
                        ))

            # --- Step 5: Backlog maintenance ---
            all_backlog = (
                session.query(Issue)
                .filter_by(team_id=team.id)
                .filter(
                    Issue.sprint_id.is_(None),
                    Issue.completed_at.is_(None),
                    Issue.issue_type != "Epic",
                )
                .all()
            )
            deficit = check_backlog_depth(len(all_backlog), team.backlog_depth_target)
            if deficit > 0:
                generated = await generate_issues(
                    count=min(deficit, 5),
                    team_name=team.name,
                    content_generator=TemplateContentGenerator(rng=self._rng),
                    rng=self._rng,
                )

                from app.engine.backlog import _EPIC_THEMES
                current_epic = _get_or_create_epic(
                    session, team, all_backlog, _EPIC_THEMES,
                    jira_actions, story_points_field_id, sim_reporter_field_id,
                    self._rng,
                )

                for gen_issue in generated:
                    new_issue = Issue(
                        team_id=team.id,
                        issue_type=gen_issue["issue_type"],
                        summary=gen_issue["summary"],
                        description=gen_issue["description"],
                        story_points=gen_issue["story_points"],
                        status="backlog",
                        backlog_priority=len(all_backlog) + 1,
                        epic_id=current_epic.id if current_epic else None,
                    )
                    session.add(new_issue)
                    session.flush()

                    issue_fields: dict = {
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
                    }
                    if story_points_field_id and gen_issue["story_points"]:
                        issue_fields[story_points_field_id] = gen_issue["story_points"]
                    if sim_reporter_field_id:
                        issue_fields[sim_reporter_field_id] = f"[SIM] {team.name}"
                    if current_epic and current_epic.jira_issue_key:
                        issue_fields["parent"] = {"key": current_epic.jira_issue_key}

                    jira_actions.append(JiraWriteAction(
                        operation_type="CREATE_ISSUE",
                        payload={
                            "project_key": team.jira_project_key,
                            "issue_type": gen_issue["issue_type"],
                            "summary": f"[SIM] {gen_issue['summary']}",
                            "fields": issue_fields,
                            "_board_id": team.jira_board_id,
                            "_sp_field_id": story_points_field_id,
                        },
                        issue_id=new_issue.id,
                    ))

            # --- Step 6: Enqueue Jira actions ---
            self.enqueue_actions(team.id, jira_actions, session=session)

            return TeamTickResult(
                team_id=team.id,
                jira_actions_count=len(jira_actions),
                events_fired=[],
                error=None,
            )
        except Exception as e:
            logger.exception("Team %d tick failed: %s", team.id, e)
            return TeamTickResult(
                team_id=team.id,
                jira_actions_count=0,
                events_fired=[],
                error=str(e),
            )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _get_active_or_planning_sprint(session, team_id):
    """Find the current active or planning sprint."""
    from app.engine.sprint_lifecycle import SprintPhase
    from app.models.sprint import Sprint

    return (
        session.query(Sprint)
        .filter_by(team_id=team_id)
        .filter(Sprint.phase.in_([
            SprintPhase.PLANNING.value,
            SprintPhase.ACTIVE.value,
            SprintPhase.COMPLETED.value,
        ]))
        .order_by(Sprint.start_date.desc())
        .first()
    )


def _get_prioritized_backlog(session, team_id, final_status):
    """Get backlog issues ordered: carried-over first, then by priority."""
    from app.models.issue import Issue

    return (
        session.query(Issue)
        .filter_by(team_id=team_id)
        .filter(
            Issue.sprint_id.is_(None),
            Issue.completed_at.is_(None),
            Issue.issue_type != "Epic",
            Issue.status != final_status,
        )
        .order_by(
            Issue.carried_over.desc(),  # carryover items first
            Issue.backlog_priority.asc(),
        )
        .all()
    )


def _create_next_sprint(session, team, now: datetime):
    """Create the next sprint for a team."""
    from app.engine.sprint_lifecycle import SprintPhase
    from app.models.sprint import Sprint

    # Find the highest sprint number
    last_sprint = (
        session.query(Sprint)
        .filter_by(team_id=team.id)
        .order_by(Sprint.sprint_number.desc())
        .first()
    )
    next_number = ((last_sprint.sprint_number or 0) + 1) if last_sprint else 1

    start_date = now
    if next_number == 1 and team.first_sprint_start_date:
        start_date = team.first_sprint_start_date
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=UTC)

    end_date = start_date + timedelta(days=team.sprint_length_days)

    sprint = Sprint(
        team_id=team.id,
        name=f"{team.name} Sprint {next_number}",
        start_date=start_date,
        end_date=end_date,
        status="future",
        phase=SprintPhase.PLANNING.value,
        sprint_number=next_number,
        committed_points=0,
        completed_points=0,
    )
    session.add(sprint)
    session.flush()
    logger.info("Created sprint %d for team %d: %s", next_number, team.id, sprint.name)
    return sprint


def _get_config_value(session, key: str) -> str | None:
    """Look up a value from the JiraConfig key-value store."""
    from app.models.jira_config import JiraConfig

    row = session.query(JiraConfig).filter(JiraConfig.key == key).first()
    return row.value if row else None


def _parse_holidays(holidays_json: str) -> list:
    """Parse holidays JSON string to list of date objects."""
    try:
        return json.loads(holidays_json) if holidays_json else []
    except (json.JSONDecodeError, TypeError):
        return []


EPIC_STORIES_THRESHOLD = 5


def _get_or_create_epic(
    session, team, backlog_issues, epic_themes,
    jira_actions, story_points_field_id, sim_reporter_field_id, rng,
):
    """Return an existing open epic or create a new one."""
    from app.models.issue import Issue

    latest_epic = (
        session.query(Issue)
        .filter(
            Issue.team_id == team.id,
            Issue.issue_type == "Epic",
        )
        .order_by(Issue.id.desc())
        .first()
    )

    if latest_epic:
        child_count = (
            session.query(Issue)
            .filter(Issue.epic_id == latest_epic.id)
            .count()
        )
        if child_count < EPIC_STORIES_THRESHOLD:
            return latest_epic

    theme = rng.choice(epic_themes)
    epic = Issue(
        team_id=team.id,
        issue_type="Epic",
        summary=f"[SIM] Epic: {theme}",
        description=f"Auto-generated epic for {team.name} — {theme}",
        story_points=0,
        status="backlog",
        backlog_priority=0,
    )
    session.add(epic)
    session.flush()

    issue_fields: dict = {
        "description": {
            "type": "doc",
            "version": 1,
            "content": [{
                "type": "paragraph",
                "content": [{
                    "type": "text",
                    "text": epic.description,
                }],
            }],
        },
    }
    if sim_reporter_field_id:
        issue_fields[sim_reporter_field_id] = f"[SIM] {team.name}"

    jira_actions.append(JiraWriteAction(
        operation_type="CREATE_ISSUE",
        payload={
            "project_key": team.jira_project_key,
            "issue_type": "Epic",
            "summary": epic.summary,
            "fields": issue_fields,
            "_board_id": team.jira_board_id,
            "_sp_field_id": story_points_field_id,
        },
        issue_id=epic.id,
    ))
    logger.info("Created epic %d: %s for team %d", epic.id, theme, team.id)
    return epic
