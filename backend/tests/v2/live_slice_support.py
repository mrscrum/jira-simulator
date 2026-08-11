"""Shared test builders for the v2 live-slice contract."""

import json
from datetime import UTC, datetime, timedelta

from app.v2.application.create_team import CreateTeamCommand, CreateTeamService
from app.v2.domain.canonical_json import canonical_sha256, semantic_uuid
from app.v2.domain.live_slice import (
    ActivityDetails,
    ActivityEventDraft,
    DraftEnvelope,
    GroundTruthDetails,
    GroundTruthRecordDraft,
    ProjectionDetails,
    ProjectionIntentDraft,
    RuntimeAdvance,
    TickSliceCommit,
)
from app.v2.domain.team_runtime import PersistedTeamAggregate
from app.v2.persistence.team_repository import SqlAlchemyV2TeamRepository

SLICE_TIME = datetime(2026, 8, 10, 19, tzinfo=UTC)


def create_aggregate(
    session_factory, blueprint_json: str, requested_at: datetime
) -> PersistedTeamAggregate:
    digest = canonical_sha256(json.loads(blueprint_json))
    command = CreateTeamCommand(f"request-{digest[:12]}", blueprint_json, requested_at)
    return CreateTeamService(SqlAlchemyV2TeamRepository(session_factory)).create(command)


def draft_envelope(kind: str, index: int, occurred_at: datetime = SLICE_TIME) -> DraftEnvelope:
    return DraftEnvelope(
        semantic_key=f"slice/{kind}/{index}",
        schema_version="1.0",
        occurred_at=occurred_at,
        payload={"index": index, "kind": kind},
    )


def activity_drafts(
    aggregate: PersistedTeamAggregate, label: str
) -> tuple[ActivityEventDraft, ...]:
    details = ActivityDetails("ISSUE_UPDATED", "ISSUE", aggregate.team.id, 7)
    return tuple(
        ActivityEventDraft.create(draft_envelope(f"{label}/activity", index), details)
        for index in (1, 2)
    )


def ground_truth_drafts(label: str) -> tuple[GroundTruthRecordDraft, ...]:
    details = GroundTruthDetails("ISSUE_STATE", "SIMULATOR_V1")
    return tuple(
        GroundTruthRecordDraft.create(draft_envelope(f"{label}/ground", index), details)
        for index in (1, 2)
    )


def projection_drafts(
    aggregate: PersistedTeamAggregate, label: str
) -> tuple[ProjectionIntentDraft, ...]:
    details = ProjectionDetails("JIRA", "UPSERT_ISSUE", aggregate.team.id, 7, "PENDING")
    return tuple(
        ProjectionIntentDraft.create(draft_envelope(f"{label}/projection", index), details)
        for index in (1, 2)
    )


def make_tick_commit(
    aggregate: PersistedTeamAggregate, expected_version: int, label: str
) -> TickSliceCommit:
    simulation_time = SLICE_TIME + timedelta(minutes=expected_version + 1)
    return TickSliceCommit(
        commit_id=semantic_uuid(f"commit/{aggregate.team.id}/{label}"),
        team_id=aggregate.team.id,
        run_id=aggregate.run.id,
        expected_runtime_version=expected_version,
        runtime_after=RuntimeAdvance(
            "RUNNING", simulation_time, simulation_time + timedelta(hours=1)
        ),
        activity=activity_drafts(aggregate, label),
        ground_truth=ground_truth_drafts(label),
        projection_intents=projection_drafts(aggregate, label),
        recorded_at=simulation_time,
    )
