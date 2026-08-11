import json
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from functools import partial
from pathlib import Path
from uuid import UUID

import pytest

from app.v2.application.create_team import CreateTeamCommand, CreateTeamService
from app.v2.domain.canonical_json import canonical_sha256
from app.v2.domain.deterministic_rng import (
    CreationKind,
    DecisionOccurrence,
    DecisionType,
    DeterministicRandomStream,
    dependency_rng_id,
    item_rng_id,
    member_rng_id,
    rework_rng_id,
    run_rng_id,
    sprint_rng_id,
    team_rng_id,
    visit_rng_id,
)

BLUEPRINT_DIGEST = "830ea9fac498205061f1bdcd0741664cafddefba102d3f0c209102efc9820276"
TEAM_ID = UUID("30a7c8bc-aa8f-5c80-af37-6e5fe3f516d6")
RUN_ID = UUID("bdaf2033-9766-55f7-abf2-2cc41a15c10e")
ITEM_ID = UUID("8f317d4f-8156-5b43-9571-6b3b32d32304")
VISIT_ID = UUID("0e45dd9b-8583-5863-bbc7-af9dfe5c0a43")
VECTOR_NAMES = (
    "composed_unicode_seed",
    "decomposed_unicode_seed",
    "distinct_unicode_seed",
    "positive_occurrence_and_draw",
)


def _golden_vectors() -> list[dict[str, object]]:
    fixture = Path(__file__).parents[1] / "fixtures" / "hmac_sha256_u53_v1_vectors.json"
    return json.loads(fixture.read_text(encoding="utf-8"))["vectors"]


def _golden_vector(name: str) -> dict[str, object]:
    return next(vector for vector in _golden_vectors() if vector["name"] == name)


def _draw_from_vector(vector: dict[str, object]):
    entity_text = str(vector["entity_id"])
    entity_id = UUID(entity_text) if entity_text.count("-") == 4 else entity_text
    decision = DecisionOccurrence(
        entity_id,
        DecisionType(str(vector["decision_type"])),
        int(vector["occurrence"]),
    )
    stream = DeterministicRandomStream(
        str(vector["seed"]), UUID(str(vector["team_id"])), UUID(str(vector["run_id"]))
    )
    return stream.draw(decision, int(vector["draw_index"]))


def _fresh_process_script(vector: dict[str, object]) -> str:
    return f"""
import json
from uuid import UUID
from app.v2.domain.deterministic_rng import (
    DecisionOccurrence, DecisionType, DeterministicRandomStream,
)
stream = DeterministicRandomStream(
    {vector["seed"]!r}, UUID({vector["team_id"]!r}), UUID({vector["run_id"]!r})
)
decision = DecisionOccurrence(
    {vector["entity_id"]!r}, DecisionType.RISK_CANCELLATION_OUTCOME, 7
)
draw = stream.draw(decision, 3)
result = [draw.canonical_message.decode(), draw.hmac_sha256, draw.u53_integer, draw.unit_value]
print(json.dumps(result))
"""


def test_creation_kind_is_the_closed_approved_set():
    assert tuple(kind.value for kind in CreationKind) == (
        "INITIAL_BACKLOG",
        "SCRUM_REPLENISHMENT",
        "KANBAN_ARRIVAL",
        "AGENT_CREATED",
        "JIRA_IMPORTED",
    )


def test_decision_type_is_the_closed_approved_set():
    assert tuple(decision.value for decision in DecisionType) == (
        "BACKLOG_ISSUE_TYPE",
        "BACKLOG_STORY_POINTS",
        "BACKLOG_PRIORITY",
        "ITEM_DESCRIPTION_QUALITY",
        "ITEM_LATENT_COMPLEXITY",
        "STATUS_DWELL",
        "STATUS_TOUCH",
        "SCRUM_CAPACITY_TARGET",
        "RISK_EXTERNAL_DEPENDENCY_OUTCOME",
        "RISK_EXTERNAL_DEPENDENCY_DURATION",
        "RISK_CANCELLATION_OUTCOME",
        "RISK_REVIEW_REJECTION_OUTCOME",
        "RISK_REWORK_DURATION",
        "RISK_MEMBER_UNAVAILABLE_OUTCOME",
        "RISK_MEMBER_UNAVAILABLE_DURATION",
        "FORCED_REWORK_DURATION",
        "KANBAN_ARRIVAL_GAP",
        "KANBAN_CLASS_OF_SERVICE",
    )


def test_team_run_member_and_sprint_paths_have_fixed_uuid5_vectors():
    assert team_rng_id(BLUEPRINT_DIGEST) == TEAM_ID
    assert run_rng_id(TEAM_ID, 0) == RUN_ID
    assert run_rng_id(TEAM_ID, 7) == UUID("225606fc-5044-5c3a-911f-44fd9f316efd")
    assert member_rng_id(TEAM_ID, 0) == UUID("867b58b0-43d3-5956-960a-2a291ac6258d")
    assert member_rng_id(TEAM_ID, 3) == UUID("ca369c81-3623-5413-bf29-0aa1c1b58868")
    assert sprint_rng_id(TEAM_ID, 0) == UUID("a7f24acf-7179-565e-ae21-aad23463f697")
    assert sprint_rng_id(TEAM_ID, 4) == UUID("4472c19c-781f-59c4-bc7a-738fedbfb03c")


@pytest.mark.parametrize(
    ("kind", "zero_expected", "nine_expected"),
    [
        (
            CreationKind.INITIAL_BACKLOG,
            "8f317d4f-8156-5b43-9571-6b3b32d32304",
            "bb6f58d9-2d52-525b-bcb5-f78e54388dd0",
        ),
        (
            CreationKind.SCRUM_REPLENISHMENT,
            "7b7914fd-512d-5894-a8a3-79e261b66ca8",
            "553c31d6-0c90-5f20-8ad1-b035c77b3fd5",
        ),
        (
            CreationKind.KANBAN_ARRIVAL,
            "2a1e77a5-dd11-520b-9bce-357e6ada8885",
            "227beaf5-96b8-5f26-93c2-c880a3b3b7f5",
        ),
        (
            CreationKind.AGENT_CREATED,
            "8c513178-e094-56c1-9c7c-d0a92ad50132",
            "a6f8e257-c805-5028-8fb1-05008b084d8b",
        ),
        (
            CreationKind.JIRA_IMPORTED,
            "1132fabb-1390-5b87-b4a6-90f64c507028",
            "b8d5b45d-dbc6-5b3e-ae2b-7d5a203428f8",
        ),
    ],
)
def test_every_item_creation_kind_has_zero_and_positive_vectors(
    kind: CreationKind, zero_expected: str, nine_expected: str
):
    assert item_rng_id(TEAM_ID, kind, 0) == UUID(zero_expected)
    assert item_rng_id(TEAM_ID, kind, 9) == UUID(nine_expected)


def test_visit_dependency_and_rework_paths_have_fixed_vectors():
    assert visit_rng_id(ITEM_ID, 0) == VISIT_ID
    assert visit_rng_id(ITEM_ID, 5) == UUID("c6f73387-769e-57a3-97da-a9d228a7a8ae")
    assert dependency_rng_id(VISIT_ID, 0) == UUID("67131548-6cf0-574d-a7bc-3a716f605a10")
    assert dependency_rng_id(VISIT_ID, 6) == UUID("f71baa2c-7fde-52dd-bf5b-6060c87efb26")
    assert rework_rng_id(ITEM_ID, 0) == UUID("8070b6a9-cd90-5b14-977e-46bf7f5354d8")
    assert rework_rng_id(ITEM_ID, 2) == UUID("6ccfc162-7c41-5192-a233-0d688a35e3a1")


@pytest.mark.parametrize(
    "digest",
    ["", "0" * 63, "0" * 65, "G" * 64, BLUEPRINT_DIGEST.upper(), 7, None],
)
def test_team_path_rejects_malformed_blueprint_digest(digest: object):
    with pytest.raises((TypeError, ValueError)):
        team_rng_id(digest)


@pytest.mark.parametrize("ordinal", [-1, True, False, 1.0, "1"])
def test_every_ordinal_path_rejects_non_true_non_negative_integer(ordinal: object):
    calls = (
        partial(run_rng_id, TEAM_ID, ordinal),
        partial(member_rng_id, TEAM_ID, ordinal),
        partial(sprint_rng_id, TEAM_ID, ordinal),
        partial(item_rng_id, TEAM_ID, CreationKind.INITIAL_BACKLOG, ordinal),
        partial(visit_rng_id, ITEM_ID, ordinal),
        partial(dependency_rng_id, VISIT_ID, ordinal),
        partial(rework_rng_id, ITEM_ID, ordinal),
    )
    for call in calls:
        with pytest.raises((TypeError, ValueError)):
            call()


def test_every_nested_path_rejects_non_uuid_parent():
    calls = (
        partial(run_rng_id, str(TEAM_ID), 0),
        partial(member_rng_id, str(TEAM_ID), 0),
        partial(sprint_rng_id, str(TEAM_ID), 0),
        partial(item_rng_id, str(TEAM_ID), CreationKind.INITIAL_BACKLOG, 0),
        partial(visit_rng_id, str(ITEM_ID), 0),
        partial(dependency_rng_id, str(VISIT_ID), 0),
        partial(rework_rng_id, str(ITEM_ID), 0),
    )
    for call in calls:
        with pytest.raises(TypeError):
            call()


def test_item_path_requires_creation_kind_enum_not_string():
    with pytest.raises(TypeError):
        item_rng_id(TEAM_ID, "INITIAL_BACKLOG", 0)


def test_task1_team_and_initial_run_use_the_same_semantic_ids(
    resolved_blueprint_json: str, requested_at
):
    class ReturningRepository:
        def create(self, aggregate):
            return aggregate

    aggregate = CreateTeamService(ReturningRepository()).create(
        CreateTeamCommand("rng-id-proof", resolved_blueprint_json, requested_at)
    )
    blueprint_hash = canonical_sha256(json.loads(resolved_blueprint_json))

    assert team_rng_id(blueprint_hash) == aggregate.team.id
    assert run_rng_id(aggregate.team.id, 0) == aggregate.run.id


def test_semantic_paths_are_independent_of_call_order_and_unrelated_ids():
    expected = item_rng_id(TEAM_ID, CreationKind.INITIAL_BACKLOG, 0)

    dependency_rng_id(VISIT_ID, 99)
    member_rng_id(TEAM_ID, 42)
    actual = item_rng_id(TEAM_ID, CreationKind.INITIAL_BACKLOG, 0)

    assert actual == expected == ITEM_ID


def test_decision_occurrence_accepts_uuid_or_non_empty_catalog_key_and_is_frozen():
    uuid_decision = DecisionOccurrence(ITEM_ID, DecisionType.STATUS_DWELL, 0)
    catalog_decision = DecisionOccurrence(
        "business-date/2026-08-10", DecisionType.RISK_CANCELLATION_OUTCOME, 7
    )

    assert uuid_decision.entity_id == ITEM_ID
    assert catalog_decision.occurrence == 7
    with pytest.raises(FrozenInstanceError):
        uuid_decision.occurrence = 1


@pytest.mark.parametrize(
    ("entity_id", "decision_type", "occurrence"),
    [
        ("", DecisionType.STATUS_DWELL, 0),
        (7, DecisionType.STATUS_DWELL, 0),
        (ITEM_ID, "STATUS_DWELL", 0),
        (ITEM_ID, DecisionType.STATUS_DWELL, -1),
        (ITEM_ID, DecisionType.STATUS_DWELL, True),
    ],
)
def test_decision_occurrence_rejects_invalid_coordinates(
    entity_id: object, decision_type: object, occurrence: object
):
    with pytest.raises((TypeError, ValueError)):
        DecisionOccurrence(entity_id, decision_type, occurrence)


@pytest.mark.parametrize("name", VECTOR_NAMES)
def test_draw_matches_independently_fixed_golden_vector(name: str):
    vector = _golden_vector(name)

    draw = _draw_from_vector(vector)

    assert draw.algorithm == "HMAC_SHA256_U53_V1"
    assert draw.canonical_message == str(vector["canonical_message"]).encode("utf-8")
    assert draw.hmac_sha256 == vector["hmac_sha256"]
    assert draw.u53_integer == vector["u53_integer"]
    assert draw.unit_value == vector["unit_value"]
    assert 0 <= draw.unit_value < 1


def test_nfc_equivalent_seeds_replay_and_distinct_seed_separates():
    composed = _draw_from_vector(_golden_vector("composed_unicode_seed"))
    decomposed = _draw_from_vector(_golden_vector("decomposed_unicode_seed"))
    distinct = _draw_from_vector(_golden_vector("distinct_unicode_seed"))

    assert composed == decomposed
    assert distinct.canonical_message == composed.canonical_message
    assert distinct.hmac_sha256 != composed.hmac_sha256
    assert distinct.unit_value != composed.unit_value


def test_reversed_interleaved_and_fresh_stream_draw_order_is_irrelevant():
    stream = DeterministicRandomStream("fixed-root", TEAM_ID, RUN_ID)
    decisions = tuple(
        DecisionOccurrence(ITEM_ID, decision_type, index)
        for index, decision_type in enumerate(tuple(DecisionType)[:4])
    )
    expected = {decision: stream.draw(decision, 2) for decision in decisions}

    actual = {}
    for decision in reversed(decisions):
        stream.draw(DecisionOccurrence(VISIT_ID, DecisionType.STATUS_TOUCH, 99), 17)
        actual[decision] = stream.draw(decision, 2)
    fresh = DeterministicRandomStream("fixed-root", TEAM_ID, RUN_ID)

    assert actual == expected
    assert {decision: fresh.draw(decision, 2) for decision in decisions} == expected


def test_fixed_draw_replays_in_a_fresh_python_process():
    vector = _golden_vector("positive_occurrence_and_draw")
    completed = subprocess.run(
        [sys.executable, "-B", "-c", _fresh_process_script(vector)],
        cwd=Path(__file__).parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == [
        vector["canonical_message"],
        vector["hmac_sha256"],
        vector["u53_integer"],
        vector["unit_value"],
    ]


@pytest.mark.parametrize("draw_index", [-1, True, False, 1.0, "1"])
def test_draw_rejects_non_true_non_negative_draw_index(draw_index: object):
    stream = DeterministicRandomStream("fixed-root", TEAM_ID, RUN_ID)
    decision = DecisionOccurrence(ITEM_ID, DecisionType.STATUS_DWELL, 0)

    with pytest.raises((TypeError, ValueError)):
        stream.draw(decision, draw_index)


def test_stream_rejects_invalid_seed_and_uuid_boundaries():
    invalid_arguments = (
        ("", TEAM_ID, RUN_ID),
        (7, TEAM_ID, RUN_ID),
        ("seed", str(TEAM_ID), RUN_ID),
        ("seed", TEAM_ID, str(RUN_ID)),
    )
    for arguments in invalid_arguments:
        with pytest.raises((TypeError, ValueError)):
            DeterministicRandomStream(*arguments)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("algorithm", "OTHER"),
        ("draw_index", True),
        ("canonical_message", "not-bytes"),
        ("canonical_message", b"{}"),
        ("hmac_sha256", "A" * 64),
        ("hmac_sha256", "0" * 64),
        ("u53_integer", True),
        ("u53_integer", 2**53),
        ("unit_value", float("nan")),
        ("unit_value", 0.5),
    ],
)
def test_uniform_draw_rejects_invalid_or_decoupled_provenance(field: str, value: object):
    draw = _draw_from_vector(_golden_vector("composed_unicode_seed"))

    with pytest.raises((TypeError, ValueError)):
        replace(draw, **{field: value})


def test_uniform_draw_and_stream_are_frozen():
    stream = DeterministicRandomStream("fixed-root", TEAM_ID, RUN_ID)
    decision = DecisionOccurrence(ITEM_ID, DecisionType.STATUS_TOUCH, 0)
    draw = stream.draw(decision)

    with pytest.raises(FrozenInstanceError):
        stream.root_seed = "changed"
    with pytest.raises(FrozenInstanceError):
        draw.unit_value = 0.5
