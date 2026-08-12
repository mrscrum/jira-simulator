"""Production composition of durable Jira provisioning intents."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.v2.application.live_team import LiveTeamState
from app.v2.domain.canonical_json import semantic_uuid
from app.v2.domain.live_slice import (
    DraftEnvelope,
    ProjectionDetails,
    ProjectionIntentDraft,
    RuntimeAdvance,
    TickSliceCommit,
)
from app.v2.domain.scrum_state import SprintLifecycle, SprintState, WorkItemState


@dataclass(frozen=True)
class _ProvisioningContext:
    state: LiveTeamState
    recorded_at: datetime


@dataclass(frozen=True)
class _IntentSpecification:
    suffix: str
    operation: str
    aggregate_id: UUID
    payload: dict[str, object]


def compose_jira_provisioning(state: LiveTeamState) -> TickSliceCommit:
    """Build the idempotent project, board, and initial-issue provisioning slice."""
    context = _provisioning_context(state)
    return _provisioning_commit(context, _provisioning_intents(context))


def compose_initial_jira_provisioning(state: LiveTeamState) -> TickSliceCommit:
    """Build bootstrap provisioning, including an initially active sprint."""
    context = _provisioning_context(state)
    return _provisioning_commit(context, _initial_provisioning_intents(context))


def _provisioning_context(state: LiveTeamState) -> _ProvisioningContext:
    return _ProvisioningContext(state, min(item.created_at for item in state.scrum.work_items))


def _provisioning_commit(
    context: _ProvisioningContext, intents: tuple[ProjectionIntentDraft, ...]
) -> TickSliceCommit:
    state = context.state
    runtime = state.aggregate.runtime
    return TickSliceCommit(
        semantic_uuid(f"jira-provisioning/{runtime.team_id}/{runtime.run_id}"),
        runtime.team_id,
        runtime.run_id,
        runtime.version,
        RuntimeAdvance(runtime.state, runtime.simulation_time, runtime.next_wake_at),
        (),
        (),
        intents,
        context.recorded_at,
    )


def _provisioning_intents(
    context: _ProvisioningContext,
) -> tuple[ProjectionIntentDraft, ...]:
    project = _project_intent(context)
    board = _board_intent(context, project.semantic_key)
    issues = tuple(
        _issue_intent(context, work, board.semantic_key) for work in context.state.scrum.work_items
    )
    return project, board, *issues


def _initial_provisioning_intents(
    context: _ProvisioningContext,
) -> tuple[ProjectionIntentDraft, ...]:
    basics = _provisioning_intents(context)
    active = next(
        (
            sprint
            for sprint in context.state.scrum.sprints
            if sprint.lifecycle is SprintLifecycle.ACTIVE
        ),
        None,
    )
    if active is None:
        return basics
    return (*basics, *_active_sprint_intents(context, active, basics[1:]))


def _active_sprint_intents(
    context: _ProvisioningContext,
    sprint: SprintState,
    predecessors: tuple[ProjectionIntentDraft, ...],
) -> tuple[ProjectionIntentDraft, ...]:
    dependencies = [intent.semantic_key for intent in predecessors]
    created = _create_sprint_intent(context, sprint, dependencies)
    scoped = _scope_sprint_intent(context, sprint, created.semantic_key)
    started = _start_sprint_intent(context, sprint, scoped.semantic_key)
    return created, scoped, started


def _create_sprint_intent(
    context: _ProvisioningContext, sprint: SprintState, dependencies: list[str]
) -> ProjectionIntentDraft:
    blueprint = context.state.aggregate.blueprint
    payload = {
        "board_id": str(context.state.aggregate.team.id),
        "depends_on": dependencies,
        "end_at": sprint.planned_end_at.isoformat(),
        "name": f"SIM-{blueprint.jira.project_key}-{sprint.id.hex[:12]}",
        "sprint_id": str(sprint.id),
        "start_at": sprint.planned_start_at.isoformat(),
    }
    spec = _IntentSpecification(f"sprint/{sprint.id}/create", "CREATE_SPRINT", sprint.id, payload)
    return _intent(context, spec)


def _scope_sprint_intent(
    context: _ProvisioningContext, sprint: SprintState, dependency: str
) -> ProjectionIntentDraft:
    issue_ids = [
        str(entry.work_item_id)
        for entry in context.state.scrum.sprint_scope
        if entry.sprint_id == sprint.id and entry.removed_at is None
    ]
    payload = {
        "depends_on": [dependency],
        "issue_ids": issue_ids,
        "sprint_id": str(sprint.id),
    }
    spec = _IntentSpecification(f"sprint/{sprint.id}/scope", "SCOPE_SPRINT", sprint.id, payload)
    return _intent(context, spec)


def _start_sprint_intent(
    context: _ProvisioningContext, sprint: SprintState, dependency: str
) -> ProjectionIntentDraft:
    payload = {"depends_on": [dependency], "sprint_id": str(sprint.id)}
    spec = _IntentSpecification(f"sprint/{sprint.id}/start", "START_SPRINT", sprint.id, payload)
    return _intent(context, spec)


def _project_intent(context: _ProvisioningContext) -> ProjectionIntentDraft:
    state, blueprint = context.state, context.state.aggregate.blueprint
    payload = {
        "board_type": "SCRUM",
        "depends_on": [],
        "name": blueprint.jira.project_name,
        "project_key": blueprint.jira.project_key,
    }
    spec = _IntentSpecification("project", "CREATE_PROJECT", state.aggregate.team.id, payload)
    return _intent(context, spec)


def _board_intent(context: _ProvisioningContext, project_key: str) -> ProjectionIntentDraft:
    state, blueprint = context.state, context.state.aggregate.blueprint
    payload = {
        "board_type": "SCRUM",
        "depends_on": [project_key],
        "project_key": blueprint.jira.project_key,
        "project_name": blueprint.jira.project_name,
    }
    spec = _IntentSpecification("board", "CREATE_BOARD", state.aggregate.team.id, payload)
    return _intent(context, spec)


def _issue_intent(
    context: _ProvisioningContext, work: WorkItemState, board_key: str
) -> ProjectionIntentDraft:
    blueprint = context.state.aggregate.blueprint
    payload = {
        "depends_on": [board_key],
        "fields": {},
        "issue_id": str(work.id),
        "issue_type": work.issue_type.title(),
        "project_key": blueprint.jira.project_key,
        "summary": f"Simulated {work.issue_type.title()} {work.creation_sequence + 1}",
    }
    spec = _IntentSpecification(f"issue/{work.id}", "CREATE_ISSUE", work.id, payload)
    return _intent(context, spec)


def _intent(
    context: _ProvisioningContext, specification: _IntentSpecification
) -> ProjectionIntentDraft:
    state = context.state
    envelope = DraftEnvelope(
        f"jira-provisioning/{state.aggregate.team.id}/{state.aggregate.runtime.run_id}/"
        f"{specification.suffix}",
        "1.0",
        context.recorded_at,
        specification.payload,
    )
    details = ProjectionDetails(
        "JIRA", specification.operation, specification.aggregate_id, 1, "PENDING"
    )
    return ProjectionIntentDraft.create(envelope, details)
