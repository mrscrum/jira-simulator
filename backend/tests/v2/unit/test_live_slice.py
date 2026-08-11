from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields, replace
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


def _ground_truth() -> GroundTruthRecordDraft:
    details = GroundTruthDetails("ISSUE_STATE", "SIMULATOR_V1")
    return GroundTruthRecordDraft.create(
        replace(_envelope(), semantic_key="tick-1/evidence-1"), details
    )


def _projection() -> ProjectionIntentDraft:
    details = ProjectionDetails("JIRA", "UPSERT_ISSUE", TEAM_ID, 7, "PENDING")
    return ProjectionIntentDraft.create(
        replace(_envelope(), semantic_key="tick-1/projection-1"), details
    )


def _direct_constructor(draft, changes: dict[str, object]):
    values = {field.name: getattr(draft, field.name) for field in fields(draft)}
    return type(draft)(**(values | changes))


def _dataclass_replace(draft, changes: dict[str, object]):
    return replace(draft, **changes)


def test_draft_factories_derive_canonical_identity_and_normalize_utc():
    activity = _activity()
    ground = _ground_truth()
    projection = _projection()

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


@pytest.mark.parametrize(
    "draft_factory",
    [_activity, _ground_truth, _projection],
    ids=["activity", "ground-truth", "projection"],
)
@pytest.mark.parametrize(
    "construction_route",
    [_direct_constructor, _dataclass_replace],
    ids=["direct", "replace"],
)
@pytest.mark.parametrize(
    "changes",
    [
        {"id": UUID(int=1)},
        {"semantic_key": " "},
        {"schema_version": ""},
        {"occurred_at": datetime(2026, 8, 10, 19)},
        {"canonical_payload": "{"},
        {"canonical_payload": '{"z":1, "a":2}'},
        {"payload_sha256": "0" * 64},
    ],
    ids=[
        "wrong-id",
        "empty-semantic-key",
        "empty-schema-version",
        "naive-instant",
        "invalid-json",
        "noncanonical-json",
        "wrong-digest",
    ],
)
def test_public_draft_construction_revalidates_common_invariants(
    draft_factory: Callable,
    construction_route: Callable,
    changes: dict[str, object],
):
    with pytest.raises((TypeError, ValueError)):
        construction_route(draft_factory(), changes)


@pytest.mark.parametrize(
    "draft_factory,changes",
    [
        (_activity, {"event_type": ""}),
        (_activity, {"aggregate_type": ""}),
        (_activity, {"aggregate_id": "not-a-uuid"}),
        (_activity, {"aggregate_version": -1}),
        (_activity, {"aggregate_version": True}),
        (_ground_truth, {"record_type": ""}),
        (_ground_truth, {"provenance_type": ""}),
        (_projection, {"target_kind": ""}),
        (_projection, {"operation_type": ""}),
        (_projection, {"aggregate_id": "not-a-uuid"}),
        (_projection, {"aggregate_version": -1}),
        (_projection, {"aggregate_version": True}),
        (_projection, {"status": "DELIVERED"}),
    ],
)
@pytest.mark.parametrize(
    "construction_route",
    [_direct_constructor, _dataclass_replace],
    ids=["direct", "replace"],
)
def test_public_draft_construction_revalidates_type_specific_invariants(
    draft_factory: Callable,
    changes: dict[str, object],
    construction_route: Callable,
):
    with pytest.raises((TypeError, ValueError)):
        construction_route(draft_factory(), changes)


def test_draft_envelope_payload_rejects_every_alias_and_nested_mutation():
    source = {"nested": {"value": 1}, "items": [{"value": 2}]}
    envelope = DraftEnvelope("immutable", "1.0", OCCURRED_AT, source)
    canonical_before = envelope.canonical()
    payload_alias = envelope.payload

    with pytest.raises(TypeError, match="immutable"):
        payload_alias |= {"added": True}
    with pytest.raises(TypeError, match="immutable"):
        envelope.payload["nested"]["value"] = 3
    with pytest.raises(TypeError):
        envelope.payload["items"][0] = {"value": 4}
    source["nested"]["value"] = 5
    source["items"].append({"value": 6})

    assert envelope.canonical() == canonical_before


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
