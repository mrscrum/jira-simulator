from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from app.v2.domain.canonical_json import canonical_json, canonical_sha256, semantic_uuid
from app.v2.domain.deterministic_rng import (
    CreationKind,
    DecisionOccurrence,
    DecisionType,
    DeterministicRandomStream,
    item_rng_id,
    member_rng_id,
    sprint_rng_id,
    visit_rng_id,
)
from app.v2.domain.sampling import DwellAnchors, TouchBounds, sample_dwell, sample_touch
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
    StatusVisitState,
    WorkItemFactor,
    WorkItemLifecycle,
    WorkItemState,
    WorkPriority,
)
from app.v2.persistence.team_models import V2RunModel, V2TeamModel

TEAM_ID = UUID("b04d60fb-bb7e-5ef9-a005-679e1b24d3f5")
RUN_ID = UUID("dad7f46e-af1f-5d28-9e09-28d287149de5")
MEMBER_ID = member_rng_id(TEAM_ID, 0)
ITEM_ID = item_rng_id(TEAM_ID, CreationKind.INITIAL_BACKLOG, 0)
SPRINT_ID = sprint_rng_id(TEAM_ID, 0)
VISIT_ID = visit_rng_id(ITEM_ID, 0)
NOW = datetime(2026, 8, 10, 18, 30, tzinfo=UTC)
LATER = NOW + timedelta(hours=4)
BUSINESS_DATE = date(2026, 8, 10)


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
    return MemberIdentity(MEMBER_ID, TEAM_ID, 0)


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
        5,
        WorkPriority.HIGH,
        2,
        WorkItemLifecycle.ACTIVE,
        "development",
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
        "development",
        "DEVELOPMENT",
        MEMBER_ID,
        NOW,
        None,
        7_200_000_000,
        1_800_000_000,
        5_400_000_000,
        300_000_000,
        0,
        1_800_000_000,
    )


def make_sample() -> StatusVisitSample:
    dwell_draw, touch_draw, dwell, touch, provenance = _sample_inputs()
    dwell_parameters, touch_parameters, dwell_provenance, touch_provenance = provenance
    required_document = {"required_work_microseconds": 7_200_000_000}
    return StatusVisitSample(
        VISIT_ID,
        TEAM_ID,
        RUN_ID,
        "SCRUM_DEFAULT",
        "1.0",
        "DWELL_LOG_PIECEWISE_V1",
        "TOUCH_LINEAR_V1",
        *dwell_parameters,
        *touch_parameters,
        *dwell_provenance,
        *touch_provenance,
        dwell_draw.unit_value,
        touch_draw.unit_value,
        dwell.sampled_hours,
        touch.sampled_hours,
        7_200_000_000,
        canonical_sha256(required_document),
    )


def _sample_inputs() -> tuple[object, ...]:
    stream = DeterministicRandomStream("task-5-seed", TEAM_ID, RUN_ID)
    dwell_draw = stream.draw(DecisionOccurrence(VISIT_ID, DecisionType.STATUS_DWELL, 0), 0)
    touch_draw = stream.draw(DecisionOccurrence(VISIT_ID, DecisionType.STATUS_TOUCH, 0), 0)
    anchors = DwellAnchors(0.0, 0.5, 1.0, 3.0, 4.0)
    bounds = TouchBounds(1.0, 3.0)
    dwell = sample_dwell(anchors, dwell_draw.unit_value)
    touch = sample_touch(bounds, touch_draw.unit_value)
    dwell_parameters = _canonical_pair(
        {"maximum": 4.0, "minimum": 0.0, "p25": 0.5, "p50": 1.0, "p99": 3.0}
    )
    touch_parameters = _canonical_pair({"maximum": 3.0, "minimum": 1.0})
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
        session.add(
            V2TeamModel(
                id=str(TEAM_ID),
                idempotency_key="task-5-parent",
                blueprint_sha256="1" * 64,
                name="Task 5 Team",
                methodology="SCRUM",
                created_at=NOW,
            )
        )
        session.flush()
        session.add(
            V2RunModel(
                id=str(RUN_ID),
                team_id=str(TEAM_ID),
                ordinal=0,
                state="ACTIVE",
                created_at=NOW,
            )
        )


def for_team_run(state: ScrumStateWriteSet, team_id: UUID, run_id: UUID) -> ScrumStateWriteSet:
    values = {}
    for field_name in state.__dataclass_fields__:
        records = getattr(state, field_name)
        values[field_name] = tuple(
            replace(record, team_id=team_id, run_id=run_id) for record in records
        )
    return replace(state, **values)
