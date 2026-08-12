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
from app.v2.domain.scrum_state import WorkItemState


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
    runtime = state.aggregate.runtime
    recorded_at = min(item.created_at for item in state.scrum.work_items)
    context = _ProvisioningContext(state, recorded_at)
    return TickSliceCommit(
        semantic_uuid(f"jira-provisioning/{runtime.team_id}/{runtime.run_id}"),
        runtime.team_id,
        runtime.run_id,
        runtime.version,
        RuntimeAdvance(runtime.state, runtime.simulation_time, runtime.next_wake_at),
        (),
        (),
        _provisioning_intents(context),
        recorded_at,
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
