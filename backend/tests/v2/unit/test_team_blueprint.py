import json
import math
from copy import deepcopy
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.v2.domain.canonical_json import canonical_json, canonical_sha256, semantic_uuid
from app.v2.domain.team_blueprint import ResolvedTeamBlueprint


def _canonical_document(document: dict[str, object]) -> str:
    return canonical_json(document)


def _rejects(document: dict[str, object]) -> None:
    with pytest.raises((ValidationError, ValueError)):
        ResolvedTeamBlueprint.from_canonical_json(_canonical_document(document))


def test_resolved_blueprint_round_trips_as_deeply_frozen_model(
    resolved_blueprint_json: str,
):
    blueprint = ResolvedTeamBlueprint.from_canonical_json(resolved_blueprint_json)

    assert blueprint.canonical_json() == resolved_blueprint_json
    assert blueprint.team.name == "Payments Platform"
    assert blueprint.team.purpose.startswith("Exercise sprint-risk")
    assert blueprint.members[1].availability[0].starts_at.utcoffset().total_seconds() == 0
    with pytest.raises((ValidationError, TypeError)):
        blueprint.team.name = "Mutated"
    with pytest.raises(TypeError):
        blueprint.members[0].roles[0] = "Mutated"
    with pytest.raises(TypeError):
        blueprint.backlog.issue_type_weights["BUG"] = 1.0


def test_aware_offset_instants_normalize_to_utc_and_keep_canonical_document(
    blueprint_document: dict[str, object],
):
    changed = deepcopy(blueprint_document)
    changed["scrum"]["first_boundary"] = "2026-08-13T09:00:00-07:00"
    availability = changed["members"][1]["availability"][0]
    availability["starts_at"] = "2026-08-20T09:00:00-07:00"
    availability["ends_at"] = "2026-08-20T17:00:00-07:00"
    document = _canonical_document(changed)

    blueprint = ResolvedTeamBlueprint.from_canonical_json(document)
    stored_availability = blueprint.members[1].availability[0]

    assert blueprint.scrum.first_boundary == datetime(2026, 8, 13, 16, tzinfo=UTC)
    assert stored_availability.starts_at == datetime(2026, 8, 20, 16, tzinfo=UTC)
    assert stored_availability.ends_at == datetime(2026, 8, 21, tzinfo=UTC)
    assert blueprint.scrum.first_boundary.tzinfo is UTC
    assert stored_availability.starts_at.tzinfo is UTC
    assert stored_availability.ends_at.tzinfo is UTC
    assert blueprint.canonical_json() == document


def test_canonical_helpers_have_stable_vectors():
    value = {"z": [3, 2, 1], "a": "x"}
    digest = "7e2f203baed49f5890dd215d51ea8196429ed7ac26c6716aeb9b3a6a22f24fc0"

    assert canonical_json(value) == '{"a":"x","z":[3,2,1]}'
    assert canonical_sha256(value) == digest
    assert str(semantic_uuid(f"team/{digest}")) == "96c7e253-71db-508e-b2a2-8c3b848e5898"


@pytest.mark.parametrize(
    "mutation", ["whitespace", "reordered", "missing", "extra", "kanban", "non_finite"]
)
def test_resolved_blueprint_rejects_bad_document_encoding(
    blueprint_document: dict[str, object], mutation: str
):
    changed = deepcopy(blueprint_document)
    if mutation == "whitespace":
        document = json.dumps(changed, indent=2)
    elif mutation == "reordered":
        document = json.dumps(dict(reversed(changed.items())), separators=(",", ":"))
    elif mutation == "missing":
        changed.pop("scrum")
        document = _canonical_document(changed)
    elif mutation == "extra":
        changed["unexpected"] = True
        document = _canonical_document(changed)
    elif mutation == "kanban":
        changed["team"]["methodology"] = "KANBAN"
        document = _canonical_document(changed)
    else:
        changed["members"][0]["daily_capacity_hours"] = math.inf
        document = json.dumps(changed, separators=(",", ":"), allow_nan=True)

    with pytest.raises((ValidationError, ValueError)):
        ResolvedTeamBlueprint.from_canonical_json(document)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("team", "unexpected"), True),
        (("members", 0, "unexpected"), True),
        (("workflow", "statuses", 0, "unexpected"), True),
        (("timing", "entries"), []),
        (("risks", "rules"), []),
        (("scrum", "first_boundary"), "2026-08-13T16:00:00"),
        (("members", 1, "availability", 0, "starts_at"), "2026-08-20T16:00:00"),
    ],
)
def test_resolved_blueprint_rejects_nested_extra_incomplete_or_non_utc_values(
    blueprint_document: dict[str, object], path: tuple[object, ...], value: object
):
    changed = deepcopy(blueprint_document)
    target = changed
    for segment in path[:-1]:
        target = target[segment]
    target[path[-1]] = value

    _rejects(changed)


@pytest.mark.parametrize(
    "mutation", ["unknown_status", "missing_grid", "bad_anchor", "unsupported_activity", "overlap"]
)
def test_resolved_blueprint_rejects_cross_field_inconsistency(
    blueprint_document: dict[str, object], mutation: str
):
    changed = deepcopy(blueprint_document)
    if mutation == "unknown_status":
        changed["workflow"]["routes"][0]["steps"][1]["status_key"] = "UNKNOWN"
    elif mutation == "missing_grid":
        changed["backlog"]["story_point_weights"] = {"3": 0.5, "5": 0.5}
    elif mutation == "bad_anchor":
        changed["timing"]["entries"][0]["p50"] = 7
    elif mutation == "unsupported_activity":
        changed["workflow"]["routes"][0]["steps"][1]["required_activity"] = "security"
    else:
        interval = deepcopy(changed["members"][1]["availability"][0])
        interval["starts_at"] = "2026-08-20T18:00:00Z"
        changed["members"][1]["availability"].append(interval)

    _rejects(changed)
