import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import UUID

from app.v2.domain.canonical_json import canonical_json, canonical_sha256, semantic_uuid
from app.v2.domain.deterministic_rng import (
    CreationKind,
    DecisionOccurrence,
    DecisionType,
    DeterministicRandomStream,
    item_rng_id,
    member_rng_id,
    run_rng_id,
    sprint_rng_id,
    team_rng_id,
    visit_rng_id,
)
from app.v2.domain.sampling import dwell_anchors, sample_dwell, sample_touch, touch_bounds
from app.v2.domain.scrum_state import (
    FactorKind,
    MemberAvailabilityOverlay,
    MemberBusinessDateConsumption,
    MemberIdentity,
    NaturalDecisionEvaluation,
    ScrumStateWriteSet,
    SemanticCounter,
    SemanticCounterKind,
    SemanticCounterScope,
    SprintLifecycle,
    SprintScopeEntry,
    SprintState,
    StatusVisitLifecycle,
    StatusVisitSample,
    StatusVisitSampleInput,
    StatusVisitState,
    WorkItemFactor,
    WorkItemLifecycle,
    WorkItemState,
    WorkPriority,
)
from app.v2.domain.team_blueprint import ResolvedTeamBlueprint
from app.v2.persistence.team_models import V2RunModel, V2TeamBlueprintModel, V2TeamModel

BLUEPRINT_JSON = (
    Path(__file__).parent.joinpath("fixtures/resolved_scrum_blueprint.json")
    .read_text(encoding="utf-8")
    .strip()
)
BLUEPRINT = ResolvedTeamBlueprint.from_canonical_json(BLUEPRINT_JSON)
BLUEPRINT_SHA256 = canonical_sha256(json.loads(BLUEPRINT_JSON))
TEAM_ID = team_rng_id(BLUEPRINT_SHA256)
RUN_ID = run_rng_id(TEAM_ID, 0)
MEMBER_INDEX = 1
MEMBER_ID = member_rng_id(TEAM_ID, MEMBER_INDEX)
ITEM_ID = item_rng_id(TEAM_ID, CreationKind.INITIAL_BACKLOG, 0)
SPRINT_ID = sprint_rng_id(TEAM_ID, 0)
VISIT_ID = visit_rng_id(ITEM_ID, 0)
NOW = datetime(2026, 8, 10, 18, 30, tzinfo=UTC)
LATER = NOW + timedelta(hours=4)
BUSINESS_DATE = date(2026, 8, 10)
REQUIRED_WORK_MICROSECONDS = 8_647_914_917
ZERO_TOUCH_TIMING = {
    "TO_DO": (0.25, 1.0, 2.0, 8.0, 16.0),
    "DONE": (0.0, 0.0, 0.0, 0.0, 0.0),
}


def _canonical_pair(document: dict[str, object]) -> tuple[str, str]:
    return canonical_json(document), canonical_sha256(document)


def _draw_document(draw) -> dict[str, object]:
    return {
        "algorithm": draw.algorithm,
        "canonical_message": draw.canonical_message.decode("utf-8"),
        "decision_type": draw.decision.decision_type.value,
        "draw_index": draw.draw_index,
        "entity_id": str(draw.decision.entity_id),
        "hmac_sha256": draw.hmac_sha256,
        "occurrence": draw.decision.occurrence,
        "u53_integer": draw.u53_integer,
        "unit_value": draw.unit_value,
    }


def make_member() -> MemberIdentity:
    return MemberIdentity(MEMBER_ID, TEAM_ID, MEMBER_INDEX)


def make_overlay() -> MemberAvailabilityOverlay:
    provenance, digest = _canonical_pair({"source": "planned-leave", "version": 1})
    return MemberAvailabilityOverlay(
        semantic_uuid(f"overlay/{MEMBER_ID}/0"),
        TEAM_ID,
        RUN_ID,
        MEMBER_ID,
        "PLANNED_LEAVE",
        NOW,
        LATER,
        0.25,
        7_200_000_000,
        "medical appointment",
        provenance,
        digest,
        NOW,
    )


def make_consumption() -> MemberBusinessDateConsumption:
    return MemberBusinessDateConsumption(TEAM_ID, RUN_ID, MEMBER_ID, BUSINESS_DATE, 3_600_000_000)


def make_work_item() -> WorkItemState:
    return WorkItemState(
        ITEM_ID,
        TEAM_ID,
        RUN_ID,
        CreationKind.INITIAL_BACKLOG,
        0,
        "STORY",
        3,
        WorkPriority.HIGH,
        2,
        WorkItemLifecycle.ACTIVE,
        "DEVELOPMENT",
        NOW,
        NOW,
    )


def make_factor() -> WorkItemFactor:
    provenance, digest = _canonical_pair({"decision": "quality", "unit": 0.625})
    return WorkItemFactor(
        semantic_uuid(f"factor/{ITEM_ID}/{FactorKind.DESCRIPTION_QUALITY.value}"),
        TEAM_ID,
        RUN_ID,
        ITEM_ID,
        FactorKind.DESCRIPTION_QUALITY,
        0.625,
        provenance,
        digest,
        NOW,
    )


def make_sprint() -> SprintState:
    return SprintState(
        SPRINT_ID,
        TEAM_ID,
        RUN_ID,
        0,
        SprintLifecycle.ACTIVE,
        NOW,
        NOW + timedelta(days=14),
        NOW,
        None,
        NOW,
        NOW,
    )


def make_scope() -> SprintScopeEntry:
    return SprintScopeEntry(
        semantic_uuid(f"sprint-scope/{SPRINT_ID}/{ITEM_ID}"),
        TEAM_ID,
        RUN_ID,
        SPRINT_ID,
        ITEM_ID,
        NOW,
        None,
    )


def make_visit() -> StatusVisitState:
    return StatusVisitState(
        VISIT_ID,
        TEAM_ID,
        RUN_ID,
        ITEM_ID,
        0,
        StatusVisitLifecycle.OPEN,
        "DEVELOPMENT",
        "development",
        MEMBER_ID,
        NOW,
        None,
        REQUIRED_WORK_MICROSECONDS,
        1_800_000_000,
        REQUIRED_WORK_MICROSECONDS - 1_800_000_000,
        300_000_000,
        0,
        1_800_000_000,
    )


def make_sample() -> StatusVisitSample:
    return make_sample_for(BLUEPRINT, make_work_item(), make_visit())


def make_sample_for(
    blueprint: ResolvedTeamBlueprint, work_item: WorkItemState, visit: StatusVisitState
) -> StatusVisitSample:
    stream = DeterministicRandomStream(blueprint.seed, work_item.team_id, work_item.run_id)
    dwell_draw = stream.draw(DecisionOccurrence(visit.id, DecisionType.STATUS_DWELL, 0), 0)
    touch_draw = stream.draw(DecisionOccurrence(visit.id, DecisionType.STATUS_TOUCH, 0), 0)
    sample_input = StatusVisitSampleInput(blueprint, work_item, visit, dwell_draw, touch_draw)
    return StatusVisitSample.create(sample_input)


def zero_touch_blueprint_json(status_key: str) -> str:
    minimum, p25, p50, p99, maximum = ZERO_TOUCH_TIMING[status_key]
    document = json.loads(BLUEPRINT_JSON)
    document["timing"]["entries"].append(
        {
            "issue_type": "STORY",
            "max": maximum,
            "min": minimum,
            "p25": p25,
            "p50": p50,
            "p99": p99,
            "status_key": status_key,
            "story_points": 3,
            "touch_max": 0.0,
            "touch_min": 0.0,
        }
    )
    return canonical_json(document)


def make_zero_touch_write_set(status_key: str) -> ScrumStateWriteSet:
    blueprint = ResolvedTeamBlueprint.from_canonical_json(zero_touch_blueprint_json(status_key))
    team_id = team_rng_id(canonical_sha256(json.loads(blueprint.canonical_json())))
    run_id = run_rng_id(team_id, 0)
    work_item = _zero_touch_work_item(team_id, run_id, status_key)
    visit = _zero_touch_visit(work_item, status_key)
    return ScrumStateWriteSet(
        work_items=(work_item,),
        status_visits=(visit,),
        status_visit_samples=(make_sample_for(blueprint, work_item, visit),),
    )


def _zero_touch_work_item(team_id: UUID, run_id: UUID, status_key: str) -> WorkItemState:
    lifecycle = WorkItemLifecycle.ACTIVE if status_key == "TO_DO" else WorkItemLifecycle.DONE
    return WorkItemState(
        item_rng_id(team_id, CreationKind.INITIAL_BACKLOG, 0),
        team_id,
        run_id,
        CreationKind.INITIAL_BACKLOG,
        0,
        "STORY",
        3,
        WorkPriority.HIGH,
        0,
        lifecycle,
        status_key,
        NOW,
        NOW,
    )


def _zero_touch_visit(work_item: WorkItemState, status_key: str) -> StatusVisitState:
    lifecycle = StatusVisitLifecycle.OPEN if status_key == "TO_DO" else StatusVisitLifecycle.CLOSED
    closed_at = None if lifecycle is StatusVisitLifecycle.OPEN else NOW
    return StatusVisitState(
        visit_rng_id(work_item.id, 0),
        work_item.team_id,
        work_item.run_id,
        work_item.id,
        0,
        lifecycle,
        status_key,
        None,
        None,
        NOW,
        closed_at,
        0,
        0,
        0,
        0,
        0,
        0,
    )


def _sample_inputs() -> tuple[object, ...]:
    stream = DeterministicRandomStream(BLUEPRINT.seed, TEAM_ID, RUN_ID)
    dwell_draw = stream.draw(DecisionOccurrence(VISIT_ID, DecisionType.STATUS_DWELL, 0), 0)
    touch_draw = stream.draw(DecisionOccurrence(VISIT_ID, DecisionType.STATUS_TOUCH, 0), 0)
    timing_entry = BLUEPRINT.timing.entries[0]
    anchors = dwell_anchors(timing_entry)
    bounds = touch_bounds(timing_entry)
    dwell = sample_dwell(anchors, dwell_draw.unit_value)
    touch = sample_touch(bounds, touch_draw.unit_value)
    dwell_parameters = _canonical_pair(
        {"maximum": 6.0, "minimum": 1.0, "p25": 2.0, "p50": 3.0, "p99": 5.0}
    )
    touch_parameters = _canonical_pair({"maximum": 4.0, "minimum": 1.0})
    dwell_provenance = _canonical_pair(_draw_document(dwell_draw))
    touch_provenance = _canonical_pair(_draw_document(touch_draw))
    provenance = (dwell_parameters, touch_parameters, dwell_provenance, touch_provenance)
    return dwell_draw, touch_draw, dwell, touch, provenance


def make_counter() -> SemanticCounter:
    scope = SemanticCounterScope(
        SemanticCounterKind.ITEM_SEQUENCE,
        TEAM_ID,
        CreationKind.INITIAL_BACKLOG.value,
    )
    return SemanticCounter(TEAM_ID, RUN_ID, scope, 1)


def make_evaluation() -> NaturalDecisionEvaluation:
    decision_type = DecisionType.RISK_CANCELLATION_OUTCOME
    identity = f"evaluation/{TEAM_ID}/{RUN_ID}/{decision_type.value}/{ITEM_ID}/{BUSINESS_DATE}"
    return NaturalDecisionEvaluation(
        semantic_uuid(identity),
        TEAM_ID,
        RUN_ID,
        decision_type,
        ITEM_ID,
        BUSINESS_DATE,
        0,
        semantic_uuid("commit/task-5"),
        NOW,
    )


def make_write_set() -> ScrumStateWriteSet:
    return ScrumStateWriteSet(
        member_identities=(make_member(),),
        member_availability_overlays=(make_overlay(),),
        member_business_date_consumption=(make_consumption(),),
        work_items=(make_work_item(),),
        work_item_factors=(make_factor(),),
        sprints=(make_sprint(),),
        sprint_scope=(make_scope(),),
        status_visits=(make_visit(),),
        status_visit_samples=(make_sample(),),
        semantic_counters=(make_counter(),),
        natural_decision_evaluations=(make_evaluation(),),
    )


def seed_parent_team_and_run(session_factory) -> None:
    with session_factory.begin() as session:
        session.add(_team_model())
        session.flush()
        session.add_all((_blueprint_model(), _run_model()))


def _team_model() -> V2TeamModel:
    return V2TeamModel(
        id=str(TEAM_ID),
        idempotency_key="task-5-parent",
        blueprint_sha256=BLUEPRINT_SHA256,
        name="Task 5 Team",
        methodology="SCRUM",
        created_at=NOW,
    )


def _blueprint_model() -> V2TeamBlueprintModel:
    return V2TeamBlueprintModel(
        id=str(semantic_uuid(f"blueprint/{TEAM_ID}/{BLUEPRINT_SHA256}")),
        team_id=str(TEAM_ID),
        schema_version=BLUEPRINT.schema_version,
        canonical_json=BLUEPRINT_JSON,
        sha256=BLUEPRINT_SHA256,
        recorded_at=NOW,
    )


def _run_model() -> V2RunModel:
    return V2RunModel(
        id=str(RUN_ID),
        team_id=str(TEAM_ID),
        ordinal=0,
        state="ACTIVE",
        created_at=NOW,
    )


def for_team_run(state: ScrumStateWriteSet, team_id: UUID, run_id: UUID) -> ScrumStateWriteSet:
    values = {}
    for field_name in state.__dataclass_fields__:
        records = getattr(state, field_name)
        values[field_name] = tuple(
            replace(record, team_id=team_id, run_id=run_id) for record in records
        )
    return replace(state, **values)
