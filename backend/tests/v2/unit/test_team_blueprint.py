import json
import math

import pytest
from pydantic import ValidationError

from app.v2.domain.canonical_json import canonical_json, canonical_sha256, semantic_uuid
from app.v2.domain.team_blueprint import ResolvedTeamBlueprint


def test_resolved_blueprint_round_trips_canonical_document(resolved_blueprint_json: str):
    blueprint = ResolvedTeamBlueprint.from_canonical_json(resolved_blueprint_json)

    assert blueprint.canonical_json() == resolved_blueprint_json


def test_canonical_helpers_have_stable_vectors():
    value = {"z": [3, 2, 1], "a": "x"}

    assert canonical_json(value) == '{"a":"x","z":[3,2,1]}'
    assert (
        canonical_sha256(value)
        == "7e2f203baed49f5890dd215d51ea8196429ed7ac26c6716aeb9b3a6a22f24fc0"
    )
    assert (
        str(semantic_uuid("team/7e2f203baed49f5890dd215d51ea8196429ed7ac26c6716aeb9b3a6a22f24fc0"))
        == "96c7e253-71db-508e-b2a2-8c3b848e5898"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "whitespace",
        "reordered",
        "missing",
        "extra",
        "kanban",
        "empty_cells",
        "empty_rules",
        "non_finite",
    ],
)
def test_resolved_blueprint_rejects_incomplete_or_noncanonical_document(
    blueprint_document, mutation: str
):
    if mutation == "whitespace":
        document = json.dumps(blueprint_document, indent=2)
    else:
        changed = dict(blueprint_document)
        if mutation == "reordered":
            document = json.dumps(
                {key: changed[key] for key in reversed(changed)}, separators=(",", ":")
            )
        elif mutation == "missing":
            changed.pop("scrum")
            document = canonical_json(changed)
        elif mutation == "extra":
            changed["unexpected"] = True
            document = canonical_json(changed)
        elif mutation == "kanban":
            changed["team"] = {**changed["team"], "methodology": "KANBAN"}
            document = canonical_json(changed)
        elif mutation == "empty_cells":
            changed["timing"] = {**changed["timing"], "entries": []}
            document = canonical_json(changed)
        elif mutation == "empty_rules":
            changed["risks"] = {**changed["risks"], "rules": []}
            document = canonical_json(changed)
        else:
            changed["members"] = [
                {**changed["members"][0], "daily_capacity_hours": math.inf},
                changed["members"][1],
            ]
            document = json.dumps(changed, separators=(",", ":"), allow_nan=True)

    with pytest.raises((ValidationError, ValueError)):
        ResolvedTeamBlueprint.from_canonical_json(document)
