from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.v2.domain.live_slice import (
    ActivityDetails,
    ActivityEventDraft,
    DraftEnvelope,
    GroundTruthDetails,
    GroundTruthRecordDraft,
    LedgerPageQuery,
    ProjectionDetails,
    ProjectionIntentDraft,
    ProjectionPageQuery,
    RuntimeAdvance,
    TickSliceCommit,
)

OCCURRED_AT = datetime(2026, 8, 10, 12, tzinfo=timezone(timedelta(hours=-7)))
TEAM_ID = UUID("f13f852b-4959-54fc-a939-929da9288bf9")
RUN_ID = UUID("c3a43cfa-cd9c-573d-b402-d27635564f6f")
COMMIT_ID = UUID("28f0f0a2-ee52-5c87-ab1f-4488f4b8e529")


def _envelope(semantic_key: str = "tick-1/activity-1") -> DraftEnvelope:
    return DraftEnvelope(
        semantic_key=semantic_key,
        schema_version="1.0",
        occurred_at=OCCURRED_AT,
        payload={"z": [2, 1], "a": "x"},
    )


def _activity(envelope: DraftEnvelope | None = None) -> ActivityEventDraft:
    details = ActivityDetails("ISSUE_UPDATED", "ISSUE", TEAM_ID, 7)
    return ActivityEventDraft.create(envelope or _envelope(), details)


def test_draft_factories_derive_canonical_identity_and_normalize_utc():
    activity = _activity()
    ground = GroundTruthRecordDraft.create(
        replace(_envelope(), semantic_key="tick-1/evidence-1"),
        GroundTruthDetails("ISSUE_STATE", "SIMULATOR_V1"),
    )
    projection = ProjectionIntentDraft.create(
        replace(_envelope(), semantic_key="tick-1/projection-1"),
        ProjectionDetails("JIRA", "UPSERT_ISSUE", TEAM_ID, 7, "PENDING"),
    )

    assert str(activity.id) == "5b211ca0-bcf3-540b-a184-87f1c059a2ed"
    assert activity.canonical_payload == '{"a":"x","z":[2,1]}'
    assert activity.payload_sha256 == (
        "90cdf5bf8195600fc8105a39509c6093522251a462422355451ae402781cdf39"
    )
    assert activity.occurred_at == datetime(2026, 8, 10, 19, tzinfo=UTC)
    assert str(ground.id) == "93dd7dfd-1327-5073-8426-6a94e593abe3"
    assert str(projection.id) == "53e8ab89-40f5-5750-b884-2a3d28001478"


@pytest.mark.parametrize(
    "changes",
    [
        {"semantic_key": " "},
        {"occurred_at": datetime(2026, 8, 10, 19)},
        {"payload": {"invalid": {1, 2}}},
        {"supplied_id": UUID(int=1)},
        {"supplied_payload_sha256": "0" * 64},
    ],
)
def test_draft_factory_rejects_invalid_envelope_or_supplied_identity(changes):
    with pytest.raises((TypeError, ValueError), match="semantic|aware|JSON|identifier|hash"):
        _activity(replace(_envelope(), **changes))


def test_draft_and_runtime_contracts_are_frozen_and_require_pending_projection():
    activity = _activity()
    with pytest.raises(FrozenInstanceError):
        activity.event_type = "CHANGED"
    with pytest.raises(ValueError, match="PENDING"):
        ProjectionIntentDraft.create(
            replace(_envelope(), semantic_key="tick-1/projection-1"),
            ProjectionDetails("JIRA", "UPSERT_ISSUE", TEAM_ID, 7, "DELIVERED"),
        )
    with pytest.raises(ValueError, match="aware"):
        RuntimeAdvance("RUNNING", datetime(2026, 8, 10, 19), None)


def test_tick_slice_rejects_conflicting_duplicate_semantic_key():
    first = _activity()
    second = _activity(replace(_envelope(), payload={"a": "changed"}))

    with pytest.raises(ValueError, match="duplicate semantic key"):
        TickSliceCommit(
            COMMIT_ID,
            TEAM_ID,
            RUN_ID,
            0,
            RuntimeAdvance("RUNNING", OCCURRED_AT, None),
            (first, second),
            (),
            (),
            OCCURRED_AT,
        )


@pytest.mark.parametrize(
    "query_type,after_sequence,limit",
    [
        (LedgerPageQuery, -1, 10),
        (LedgerPageQuery, None, 0),
        (ProjectionPageQuery, None, 101),
    ],
)
def test_page_queries_reject_invalid_cursor_or_limit(query_type, after_sequence, limit):
    with pytest.raises(ValueError, match="sequence|limit"):
        query_type(TEAM_ID, None, after_sequence, limit)
