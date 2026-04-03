"""Mutable snapshot dataclasses mirroring ORM model attribute interfaces.

The existing pure functions (workflow_engine, capacity, sprint_lifecycle)
use attribute access on issue/step/member objects.  These snapshots
replicate that interface so pre-computation can run entirely in-memory
without touching the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class IssueSnapshot:
    """Mirrors Issue ORM fields accessed by workflow_engine and sprint_lifecycle."""

    id: int
    team_id: int
    issue_type: str
    story_points: int | None
    summary: str
    jira_issue_key: str | None
    jira_issue_id: str | None
    status: str
    current_workflow_step_id: int | None
    current_worker_id: int | None
    sampled_full_time: float = 0.0
    sampled_work_time: float = 0.0
    elapsed_full_time: float = 0.0
    elapsed_work_time: float = 0.0
    work_started: bool = False
    completed_at: datetime | None = None
    sprint_id: int | None = None
    carried_over: bool = False
    backlog_priority: int | None = None
    priority: str = "Medium"
    description: str | None = None
    is_blocked: bool = False
    descoped: bool = False


@dataclass
class TeamSnapshot:
    """Mirrors Team ORM fields used by calendar, sprint lifecycle, and precompute."""

    id: int
    name: str
    jira_project_key: str
    jira_board_id: int | None
    sprint_length_days: int
    sprint_capacity_min: int
    sprint_capacity_max: int
    priority_randomization: bool
    tick_duration_hours: float
    timezone: str
    working_hours_start: int
    working_hours_end: int
    holidays: str  # JSON string
    sprint_cadence_rule: str | None = None
    sprint_cadence_time: str | None = None
    sprint_auto_schedule: bool = True


@dataclass
class MemberSnapshot:
    """Mirrors Member ORM fields used by capacity."""

    id: int
    role: str
    team_id: int
    is_active: bool = True


@dataclass
class WorkflowStepSnapshot:
    """Read-only snapshot of a WorkflowStep, passed to workflow engine."""

    id: int
    workflow_id: int
    jira_status: str
    order: int
    role_required: str | None = None
    roles_json: str | None = None

    @property
    def roles(self) -> list[str]:
        """Return list of roles, matching WorkflowStep.roles property."""
        if self.roles_json:
            import json
            return json.loads(self.roles_json)
        if self.role_required:
            return [self.role_required]
        return []


@dataclass
class TouchTimeConfigSnapshot:
    """Read-only snapshot of TouchTimeConfig."""

    id: int
    workflow_step_id: int
    issue_type: str
    story_points: int
    min_hours: float
    max_hours: float
    full_time_p25: float | None = None
    full_time_p50: float | None = None
    full_time_p99: float | None = None


@dataclass
class MoveLeftConfigSnapshot:
    """Read-only snapshot of MoveLeftConfig with targets."""

    id: int
    team_id: int
    from_step_id: int
    issue_type: str | None
    base_probability: float
    targets: list[MoveLeftTargetSnapshot] = field(default_factory=list)


@dataclass
class MoveLeftTargetSnapshot:
    """Read-only snapshot of a MoveLeftTarget."""

    id: int
    to_step_id: int
    weight: float


# ---------------------------------------------------------------------------
# Factory functions: ORM → Snapshot
# ---------------------------------------------------------------------------

def issue_to_snapshot(issue) -> IssueSnapshot:
    """Convert an Issue ORM instance to an IssueSnapshot."""
    return IssueSnapshot(
        id=issue.id,
        team_id=issue.team_id,
        issue_type=issue.issue_type,
        story_points=issue.story_points,
        summary=issue.summary,
        jira_issue_key=issue.jira_issue_key,
        jira_issue_id=issue.jira_issue_id,
        status=issue.status,
        current_workflow_step_id=issue.current_workflow_step_id,
        current_worker_id=issue.current_worker_id,
        sampled_full_time=issue.sampled_full_time,
        sampled_work_time=issue.sampled_work_time,
        elapsed_full_time=issue.elapsed_full_time,
        elapsed_work_time=issue.elapsed_work_time,
        work_started=issue.work_started,
        completed_at=issue.completed_at,
        sprint_id=issue.sprint_id,
        carried_over=issue.carried_over,
        backlog_priority=issue.backlog_priority,
        priority=issue.priority,
        description=issue.description,
        is_blocked=issue.is_blocked,
        descoped=issue.descoped,
    )


def team_to_snapshot(team) -> TeamSnapshot:
    """Convert a Team ORM instance to a TeamSnapshot."""
    return TeamSnapshot(
        id=team.id,
        name=team.name,
        jira_project_key=team.jira_project_key,
        jira_board_id=team.jira_board_id,
        sprint_length_days=team.sprint_length_days,
        sprint_capacity_min=team.sprint_capacity_min,
        sprint_capacity_max=team.sprint_capacity_max,
        priority_randomization=team.priority_randomization,
        tick_duration_hours=team.tick_duration_hours,
        timezone=team.timezone,
        working_hours_start=team.working_hours_start,
        working_hours_end=team.working_hours_end,
        holidays=team.holidays,
        sprint_cadence_rule=getattr(team, "sprint_cadence_rule", None),
        sprint_cadence_time=getattr(team, "sprint_cadence_time", None),
        sprint_auto_schedule=getattr(team, "sprint_auto_schedule", True),
    )


def member_to_snapshot(member) -> MemberSnapshot:
    """Convert a Member ORM instance to a MemberSnapshot."""
    return MemberSnapshot(
        id=member.id,
        role=member.role,
        team_id=member.team_id,
        is_active=member.is_active,
    )


def workflow_step_to_snapshot(step) -> WorkflowStepSnapshot:
    """Convert a WorkflowStep ORM instance to a WorkflowStepSnapshot."""
    return WorkflowStepSnapshot(
        id=step.id,
        workflow_id=step.workflow_id,
        jira_status=step.jira_status,
        order=step.order,
        role_required=step.role_required,
        roles_json=step.roles_json,
    )


def touch_time_config_to_snapshot(ttc) -> TouchTimeConfigSnapshot:
    """Convert a TouchTimeConfig ORM instance to a snapshot."""
    return TouchTimeConfigSnapshot(
        id=ttc.id,
        workflow_step_id=ttc.workflow_step_id,
        issue_type=ttc.issue_type,
        story_points=ttc.story_points,
        min_hours=ttc.min_hours,
        max_hours=ttc.max_hours,
        full_time_p25=ttc.full_time_p25,
        full_time_p50=ttc.full_time_p50,
        full_time_p99=ttc.full_time_p99,
    )


def move_left_config_to_snapshot(cfg) -> MoveLeftConfigSnapshot:
    """Convert a MoveLeftConfig ORM instance to a snapshot."""
    targets = [
        MoveLeftTargetSnapshot(id=t.id, to_step_id=t.to_step_id, weight=t.weight)
        for t in (cfg.targets or [])
    ]
    return MoveLeftConfigSnapshot(
        id=cfg.id,
        team_id=cfg.team_id,
        from_step_id=cfg.from_step_id,
        issue_type=cfg.issue_type,
        base_probability=cfg.base_probability,
        targets=targets,
    )
