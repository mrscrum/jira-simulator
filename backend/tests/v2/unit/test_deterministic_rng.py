import json
import pickle
import subprocess
import sys
from copy import copy, deepcopy
from dataclasses import FrozenInstanceError, fields, replace
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
    UniformDraw,
    dependency_rng_id,
    item_rng_id,
    member_rng_id,
    rework_rng_id,
    run_rng_id,
    sprint_rng_id,
    team_rng_id,
    visit_rng_id,
)
from tests.v2.immutable_value_testing import tampered_pickle

BLUEPRINT_DIGEST = "830ea9fac498205061f1bdcd0741664cafddefba102d3f0c209102efc9820276"
TEAM_ID = UUID("30a7c8bc-aa8f-5c80-af37-6e5fe3f516d6")
RUN_ID = UUID("bdaf2033-9766-55f7-abf2-2cc41a15c10e")
ITEM_ID = UUID("8f317d4f-8156-5b43-9571-6b3b32d32304")
VISIT_ID = UUID("0e45dd9b-8583-5863-bbc7-af9dfe5c0a43")
MEMBER_ID = UUID("867b58b0-43d3-5956-960a-2a291ac6258d")
SPRINT_ID = UUID("a7f24acf-7179-565e-ae21-aad23463f697")
MAX_SAFE_INTEGER = 2**53 - 1
VECTOR_NAMES = (
    "composed_unicode_seed",
    "decomposed_unicode_seed",
    "distinct_unicode_seed",
    "positive_occurrence_and_draw",
    "max_safe_integer_ecmascript",
)
DECISION_COORDINATES = (
    (DecisionType.BACKLOG_ISSUE_TYPE, ITEM_ID, False),
    (DecisionType.BACKLOG_STORY_POINTS, ITEM_ID, False),
    (DecisionType.BACKLOG_PRIORITY, ITEM_ID, False),
    (DecisionType.ITEM_DESCRIPTION_QUALITY, ITEM_ID, False),
    (DecisionType.ITEM_LATENT_COMPLEXITY, ITEM_ID, False),
    (DecisionType.STATUS_DWELL, VISIT_ID, False),
    (DecisionType.STATUS_TOUCH, VISIT_ID, False),
    (DecisionType.SCRUM_CAPACITY_TARGET, SPRINT_ID, False),
    (DecisionType.RISK_EXTERNAL_DEPENDENCY_OUTCOME, VISIT_ID, False),
    (DecisionType.RISK_EXTERNAL_DEPENDENCY_DURATION, VISIT_ID, False),
    (DecisionType.RISK_CANCELLATION_OUTCOME, ITEM_ID, True),
    (DecisionType.RISK_REVIEW_REJECTION_OUTCOME, VISIT_ID, False),
    (DecisionType.RISK_REWORK_DURATION, VISIT_ID, False),
    (DecisionType.RISK_MEMBER_UNAVAILABLE_OUTCOME, MEMBER_ID, True),
    (DecisionType.RISK_MEMBER_UNAVAILABLE_DURATION, MEMBER_ID, True),
    (DecisionType.FORCED_REWORK_DURATION, VISIT_ID, True),
    (DecisionType.KANBAN_ARRIVAL_GAP, RUN_ID, True),
    (DecisionType.KANBAN_CLASS_OF_SERVICE, ITEM_ID, False),
)


def _golden_vectors() -> list[dict[str, object]]:
    fixture = Path(__file__).parents[1] / "fixtures" / "hmac_sha256_u53_v1_vectors.json"
    return json.loads(fixture.read_text(encoding="utf-8"))["vectors"]


def _golden_vector(name: str) -> dict[str, object]:
    return next(vector for vector in _golden_vectors() if vector["name"] == name)


def _draw_from_vector(vector: dict[str, object]):
    decision = DecisionOccurrence(
        UUID(str(vector["entity_id"])),
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
    UUID({vector["entity_id"]!r}), DecisionType({vector["decision_type"]!r}),
    {vector["occurrence"]}
)
draw = stream.draw(decision, {vector["draw_index"]})
result = [draw.canonical_message.decode(), draw.hmac_sha256, draw.u53_integer, draw.unit_value]
print(json.dumps(result))
"""


def _ordinal_path_calls(ordinal: object) -> tuple[object, ...]:
    return (
        partial(run_rng_id, TEAM_ID, ordinal),
        partial(member_rng_id, TEAM_ID, ordinal),
        partial(sprint_rng_id, TEAM_ID, ordinal),
        partial(item_rng_id, TEAM_ID, CreationKind.INITIAL_BACKLOG, ordinal),
        partial(visit_rng_id, ITEM_ID, ordinal),
        partial(dependency_rng_id, VISIT_ID, ordinal),
        partial(rework_rng_id, ITEM_ID, ordinal),
    )


def _direct_draw(draw: UniformDraw, **changes: object) -> UniformDraw:
    values = {field.name: getattr(draw, field.name) for field in fields(draw)}
    values.update(changes)
    return UniformDraw(**values)


def _changed_message(draw: UniformDraw, field: str, value: object) -> bytes:
    document = json.loads(draw.canonical_message)
    document[field] = value
    return json.dumps(
        document, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _rng_values() -> tuple[object, ...]:
    decision = DecisionOccurrence(ITEM_ID, DecisionType.STATUS_DWELL, 0)
    stream = DeterministicRandomStream("fixed-root", TEAM_ID, RUN_ID)
    return decision, stream, stream.draw(decision)


def _rng_mutation_cases() -> tuple[tuple[object, str, object], ...]:
    decision = DecisionOccurrence(ITEM_ID, DecisionType.STATUS_DWELL, 0)
    replacement = DecisionOccurrence(VISIT_ID, DecisionType.STATUS_TOUCH, 0)
    stream = DeterministicRandomStream("fixed-root", TEAM_ID, RUN_ID)
    draw = stream.draw(decision)
    return (
        (decision, "occurrence", 1),
        (stream, "root_seed", "changed-root"),
        (draw, "decision", replacement),
        (draw, "hmac_sha256", "0" * 64),
        (draw, "unit_value", 1.0),
    )


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


@pytest.mark.parametrize("ordinal", [-1, True, False, 1.0, "1", 2**53])
def test_every_ordinal_path_rejects_value_outside_safe_integer_domain(ordinal: object):
    for call in _ordinal_path_calls(ordinal):
        with pytest.raises((TypeError, ValueError)):
            call()


def test_every_ordinal_path_accepts_maximum_safe_integer():
    assert all(isinstance(call(), UUID) for call in _ordinal_path_calls(MAX_SAFE_INTEGER))


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


def test_decision_occurrence_accepts_scoped_semantic_uuid_and_is_frozen():
    uuid_decision = DecisionOccurrence(ITEM_ID, DecisionType.RISK_CANCELLATION_OUTCOME, 7)

    assert uuid_decision.entity_id == ITEM_ID
    assert uuid_decision.occurrence == 7
    with pytest.raises(FrozenInstanceError):
        uuid_decision.occurrence = 8


@pytest.mark.parametrize(("decision_type", "entity_id", "allows_nonzero"), DECISION_COORDINATES)
def test_every_decision_type_enforces_approved_occurrence_scope(
    decision_type: DecisionType, entity_id: UUID, allows_nonzero: bool
):
    assert DecisionOccurrence(entity_id, decision_type, 0).occurrence == 0
    if allows_nonzero:
        assert DecisionOccurrence(entity_id, decision_type, 1).occurrence == 1
    else:
        with pytest.raises(ValueError, match="occurrence"):
            DecisionOccurrence(entity_id, decision_type, 1)


@pytest.mark.parametrize("decision_type", tuple(DecisionType))
def test_every_current_decision_type_rejects_catalog_or_business_date_entity(
    decision_type: DecisionType,
):
    with pytest.raises(TypeError, match="UUID"):
        DecisionOccurrence("business-date/2026-08-10", decision_type, 0)


@pytest.mark.parametrize(
    ("entity_id", "decision_type", "occurrence"),
    [
        ("", DecisionType.STATUS_DWELL, 0),
        (7, DecisionType.STATUS_DWELL, 0),
        (ITEM_ID, "STATUS_DWELL", 0),
        (ITEM_ID, DecisionType.STATUS_DWELL, -1),
        (ITEM_ID, DecisionType.STATUS_DWELL, True),
        (ITEM_ID, DecisionType.RISK_CANCELLATION_OUTCOME, 2**53),
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
        DecisionOccurrence(ITEM_ID, decision_type, 0)
        for decision_type in tuple(DecisionType)[:4]
    )
    expected = {decision: stream.draw(decision, 2) for decision in decisions}

    actual = {}
    for decision in reversed(decisions):
        unrelated = DecisionOccurrence(ITEM_ID, DecisionType.RISK_CANCELLATION_OUTCOME, 99)
        stream.draw(unrelated, 17)
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


@pytest.mark.parametrize("draw_index", [-1, True, False, 1.0, "1", 2**53])
def test_draw_rejects_index_outside_safe_integer_domain(draw_index: object):
    stream = DeterministicRandomStream("fixed-root", TEAM_ID, RUN_ID)
    decision = DecisionOccurrence(ITEM_ID, DecisionType.STATUS_DWELL, 0)

    with pytest.raises((TypeError, ValueError)):
        stream.draw(decision, draw_index)


def test_draw_accepts_maximum_safe_index_with_ecmascript_canonical_bytes():
    vector = _golden_vector("max_safe_integer_ecmascript")

    draw = _draw_from_vector(vector)

    assert draw.decision.occurrence == MAX_SAFE_INTEGER
    assert draw.draw_index == MAX_SAFE_INTEGER
    assert draw.canonical_message == str(vector["canonical_message"]).encode("utf-8")


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


def test_uniform_draw_normal_direct_construction_is_sealed():
    draw = _draw_from_vector(_golden_vector("composed_unicode_seed"))

    with pytest.raises(TypeError):
        _direct_draw(draw)
    with pytest.raises(TypeError):
        UniformDraw()


def test_uniform_draw_dataclass_replacement_is_sealed():
    draw = _draw_from_vector(_golden_vector("composed_unicode_seed"))

    with pytest.raises(TypeError):
        replace(draw)


@pytest.mark.parametrize("integer_field", ["occurrence", "draw_index"])
def test_uniform_draw_rejects_boolean_integer_in_forged_message(integer_field: str):
    decision = DecisionOccurrence(ITEM_ID, DecisionType.RISK_CANCELLATION_OUTCOME, 1)
    draw = DeterministicRandomStream("fixed-root", TEAM_ID, RUN_ID).draw(decision, 1)
    forged_message = _changed_message(draw, integer_field, True)

    with pytest.raises((TypeError, ValueError)):
        _direct_draw(draw, canonical_message=forged_message)


@pytest.mark.parametrize(
    ("message_field", "forged_value"),
    [
        ("team_id", "225606fc-5044-5c3a-911f-44fd9f316efd"),
        ("run_id", "a7f24acf-7179-565e-ae21-aad23463f697"),
        ("entity_id", "867b58b0-43d3-5956-960a-2a291ac6258d"),
        ("decision_type", "RISK_MEMBER_UNAVAILABLE_OUTCOME"),
    ],
)
def test_uniform_draw_rejects_changed_message_with_retained_digest(
    message_field: str, forged_value: str
):
    draw = _draw_from_vector(_golden_vector("positive_occurrence_and_draw"))
    forged_message = _changed_message(draw, message_field, forged_value)

    with pytest.raises((TypeError, ValueError)):
        _direct_draw(draw, canonical_message=forged_message)


def test_uniform_draw_rejects_arbitrary_digest_with_self_consistent_u53_values():
    draw = _draw_from_vector(_golden_vector("composed_unicode_seed"))

    with pytest.raises((TypeError, ValueError)):
        _direct_draw(draw, hmac_sha256="0" * 64, u53_integer=0, unit_value=0.0)


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
def test_uniform_draw_rejects_every_previously_guarded_invalid_field(
    field: str, value: object
):
    draw = _draw_from_vector(_golden_vector("composed_unicode_seed"))

    with pytest.raises((TypeError, ValueError)):
        _direct_draw(draw, **{field: value})


def test_uniform_draw_persists_only_public_provenance_without_root_seed():
    draw = _draw_from_vector(_golden_vector("composed_unicode_seed"))

    assert tuple(field.name for field in fields(draw)) == (
        "algorithm", "decision", "draw_index", "canonical_message",
        "hmac_sha256", "u53_integer", "unit_value",
    )
    assert not hasattr(draw, "root_seed")
    assert "café-seed" not in repr(draw)


def test_uniform_draw_and_stream_are_frozen():
    stream = DeterministicRandomStream("fixed-root", TEAM_ID, RUN_ID)
    decision = DecisionOccurrence(ITEM_ID, DecisionType.STATUS_TOUCH, 0)
    draw = stream.draw(decision)

    with pytest.raises(FrozenInstanceError):
        stream.root_seed = "changed"
    with pytest.raises(FrozenInstanceError):
        draw.unit_value = 0.5


@pytest.mark.parametrize("value", _rng_values())
def test_rng_value_exposes_no_instance_dictionary(value: object):
    with pytest.raises(TypeError):
        vars(value)
    with pytest.raises(AttributeError):
        value.__dict__["tampered"] = True


@pytest.mark.parametrize(("value", "field", "tampered"), _rng_mutation_cases())
def test_rng_value_rejects_mapping_and_ordinary_attribute_tampering(
    value: object, field: str, tampered: object
):
    original = getattr(value, field)

    with pytest.raises(AttributeError):
        value.__dict__[field] = tampered
    with pytest.raises(FrozenInstanceError):
        setattr(value, field, tampered)
    assert getattr(value, field) == original


@pytest.mark.parametrize("value", _rng_values())
def test_rng_value_copy_operations_preserve_identity(value: object):
    assert copy(value) is value
    assert deepcopy(value) is value


@pytest.mark.parametrize("value", _rng_values())
def test_rng_value_rejects_pickle_serialization(value: object):
    with pytest.raises(TypeError, match="reconstructed"):
        pickle.dumps(value)


@pytest.mark.parametrize("value", _rng_values())
def test_rng_value_rejects_reduce_protocols(value: object):
    with pytest.raises(TypeError, match="reconstructed"):
        value.__reduce__()
    with pytest.raises(TypeError, match="reconstructed"):
        value.__reduce_ex__(pickle.HIGHEST_PROTOCOL)


@pytest.mark.parametrize(
    ("value_type", "tampered_state"),
    [
        (DecisionOccurrence, {"entity_id": ITEM_ID, "occurrence": True}),
        (DeterministicRandomStream, {"root_seed": "changed-root"}),
        (UniformDraw, {"hmac_sha256": "0" * 64, "u53_integer": 0, "unit_value": 0.0}),
    ],
)
def test_rng_value_rejects_tampered_pickle_state(
    value_type: type, tampered_state: dict[str, object]
):
    payload = tampered_pickle(value_type, tampered_state)

    with pytest.raises(TypeError, match="reconstructed"):
        pickle.loads(payload)
