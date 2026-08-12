"""Caller-owned-session mapping for detached authoritative Scrum state."""

import json
from dataclasses import fields
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.v2.domain.authoritative_slice import (
    AuthoritativeTickSliceCommit,
    EligibleNaturalDecisionClaim,
    SemanticCounterClaim,
)
from app.v2.domain.canonical_json import canonical_sha256, semantic_uuid
from app.v2.domain.deterministic_rng import (
    CreationKind,
    DecisionType,
    run_rng_id,
    team_rng_id,
)
from app.v2.domain.scrum_state import (
    FactorKind,
    MemberAvailabilityOverlay,
    MemberBusinessDateConsumption,
    MemberIdentity,
    NaturalDecisionEvaluation,
    ScrumStateQuery,
    ScrumStateSnapshot,
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
from app.v2.domain.team_blueprint import ResolvedTeamBlueprint
from app.v2.persistence.scrum_state_models import (
    V2MemberAvailabilityOverlayModel,
    V2MemberBusinessDateConsumptionModel,
    V2MemberIdentityModel,
    V2NaturalDecisionEvaluationModel,
    V2SemanticCounterModel,
    V2SprintModel,
    V2SprintScopeModel,
    V2StatusVisitModel,
    V2StatusVisitSampleModel,
    V2WorkItemFactorModel,
    V2WorkItemModel,
)
from app.v2.persistence.team_models import V2RunModel, V2TeamBlueprintModel, V2TeamModel

ENUM_FIELDS = {
    "creation_kind": CreationKind,
    "decision_type": DecisionType,
    "kind": FactorKind,
    "lifecycle": WorkItemLifecycle,
    "priority": WorkPriority,
}
LOAD_SPECS = (
    (V2MemberIdentityModel, MemberIdentity, ("blueprint_index", "id")),
    (V2MemberAvailabilityOverlayModel, MemberAvailabilityOverlay, ("starts_at", "id")),
    (
        V2MemberBusinessDateConsumptionModel,
        MemberBusinessDateConsumption,
        ("business_date", "member_id"),
    ),
    (V2WorkItemModel, WorkItemState, ("creation_kind", "creation_sequence", "id")),
    (V2WorkItemFactorModel, WorkItemFactor, ("work_item_id", "kind", "id")),
    (V2SprintModel, SprintState, ("ordinal", "id")),
    (V2SprintScopeModel, SprintScopeEntry, ("sprint_id", "work_item_id", "id")),
    (V2StatusVisitModel, StatusVisitState, ("work_item_id", "ordinal", "id")),
    (V2StatusVisitSampleModel, StatusVisitSample, ("visit_id",)),
    (V2SemanticCounterModel, SemanticCounter, ("kind", "scope_id", "scope_key")),
    (
        V2NaturalDecisionEvaluationModel,
        NaturalDecisionEvaluation,
        ("decision_type", "semantic_entity_id", "business_date", "id"),
    ),
)
IMMUTABLE_AFTER_IMAGE_MODELS = (
    V2MemberIdentityModel,
    V2WorkItemFactorModel,
    V2StatusVisitSampleModel,
)
IMMUTABLE_AFTER_IMAGE_FIELDS = {
    V2MemberAvailabilityOverlayModel: ("id", "team_id", "run_id", "member_id"),
    V2MemberBusinessDateConsumptionModel: (
        "team_id",
        "run_id",
        "member_id",
        "business_date",
    ),
    V2WorkItemModel: (
        "id",
        "team_id",
        "run_id",
        "creation_kind",
        "creation_sequence",
        "created_at",
    ),
    V2SprintModel: (
        "id",
        "team_id",
        "run_id",
        "ordinal",
        "planned_start_at",
        "planned_end_at",
        "created_at",
    ),
    V2SprintScopeModel: (
        "id",
        "team_id",
        "run_id",
        "sprint_id",
        "work_item_id",
        "added_at",
    ),
    V2StatusVisitModel: (
        "id",
        "team_id",
        "run_id",
        "work_item_id",
        "ordinal",
        "status_key",
        "activity_key",
        "entered_at",
    ),
}
NEW_ALLOCATION_SCOPES_KEY = "v2_task6_new_allocation_scopes"


class ScrumStateConflictError(RuntimeError):
    """A persisted immutable Scrum row differs from its supplied after-image."""


class CounterClaimStaleError(RuntimeError):
    """A semantic counter no longer matches the claimed expected-next value."""


class NaturalClaimConflictError(RuntimeError):
    """A natural eligibility or occurrence already has different content."""


class SqlAlchemyScrumStateMapper:
    """Maps authoritative state without owning a session or transaction."""

    def add(self, session: Session, state: ScrumStateWriteSet) -> ScrumStateSnapshot:
        if not isinstance(session, Session):
            raise TypeError("session must be a caller-owned Session")
        _require_clean_session(session)
        if type(state) is not ScrumStateWriteSet:
            raise TypeError("state must be a ScrumStateWriteSet")
        state.validate()
        coordinates = _state_coordinates(state)
        candidate = _candidate_snapshot(session, state, coordinates)
        for spec, items in zip(LOAD_SPECS, state._collection_values(), strict=True):
            _apply_collection(session, items, spec[0])
            session.flush()
        return candidate

    def load(self, session: Session, query: ScrumStateQuery) -> ScrumStateSnapshot:
        if not isinstance(session, Session):
            raise TypeError("session must be a caller-owned Session")
        _require_clean_session(session)
        if type(query) is not ScrumStateQuery:
            raise TypeError("query must be a ScrumStateQuery")
        with session.no_autoflush:
            blueprint = _load_authority(session, query.team_id, query.run_id)
            return _load_validated_snapshot(session, query, blueprint)

    def apply_after_images(
        self, session: Session, commit: AuthoritativeTickSliceCommit
    ) -> ScrumStateSnapshot:
        if type(commit) is not AuthoritativeTickSliceCommit:
            raise TypeError("commit must be an AuthoritativeTickSliceCommit")
        state = commit.state
        _validate_mapper_write(session, state)
        candidate = _candidate_snapshot(session, state, _state_coordinates(state))
        new_scopes: set[SemanticCounterScope] = set()
        new_work_items: set[UUID] = set()
        for spec, items in zip(LOAD_SPECS[:9], state._collection_values()[:9], strict=True):
            for item in items:
                if _apply_after_image(session, item, spec):
                    scope = _allocation_scope(item)
                    if scope is not None:
                        _require_allocation_claim(item, commit)
                        new_scopes.add(scope)
                    if type(item) is WorkItemState:
                        new_work_items.add(item.id)
            session.flush()
        _seed_owner_counters(session, commit, (new_work_items, set()))
        session.info[NEW_ALLOCATION_SCOPES_KEY] = frozenset(new_scopes)
        return candidate

    def preflight_replay(
        self, session: Session, commit: AuthoritativeTickSliceCommit
    ) -> bool:
        claims = _allocation_claims(commit)
        if not _contains_advanced_claim(session, commit, claims):
            return False
        _require_allocation_replay(session, commit, claims)
        _require_replayed_after_images(session, commit.state)
        _require_replayed_natural_claims(session, commit)
        return True

    def apply_counter_claims(
        self, session: Session, commit: AuthoritativeTickSliceCommit
    ) -> tuple[SemanticCounter, ...]:
        try:
            _preflight_natural_claims(session, commit)
            counters = tuple(
                _apply_counter_claim(session, commit, claim)
                for claim in _ordered_claims(commit.counter_claims)
            )
            session.flush()
            return counters
        finally:
            session.info.pop(NEW_ALLOCATION_SCOPES_KEY, None)

    def resolve_natural_claims(
        self, session: Session, commit: AuthoritativeTickSliceCommit
    ) -> tuple[NaturalDecisionEvaluation, ...]:
        evaluations = tuple(
            _resolve_natural_claim(session, commit, claim)
            for claim in _ordered_natural_claims(commit.natural_decision_claims)
        )
        session.flush()
        return evaluations


def _validate_mapper_write(session: Session, state: ScrumStateWriteSet) -> None:
    if not isinstance(session, Session):
        raise TypeError("session must be a caller-owned Session")
    _require_clean_session(session)
    if type(state) is not ScrumStateWriteSet:
        raise TypeError("state must be a ScrumStateWriteSet")
    state.validate()
    if state.semantic_counters or state.natural_decision_evaluations:
        raise ValueError("counter and evaluation rows must be applied through claims")


def _apply_after_image(session: Session, item: object, spec: tuple) -> bool:
    model_type, value_type, _order = spec
    identity = _model_identity(item, model_type)
    values = _record_values(item)
    model = session.get(model_type, identity, populate_existing=True)
    if model is None:
        if model_type is V2MemberIdentityModel:
            raise ScrumStateConflictError("Task 6 cannot recreate a missing member identity")
        if model_type is V2StatusVisitModel:
            _expunge_deleted_visit_identities(session, identity)
        session.add(model_type(**values))
        return True
    if model_type in IMMUTABLE_AFTER_IMAGE_MODELS:
        if _domain_record(model, value_type) != item:
            raise ScrumStateConflictError("immutable Scrum row has different content")
        return False
    _require_immutable_fields(model, values, model_type)
    _update_model(model, values)
    return False


def _allocation_claims(
    commit: AuthoritativeTickSliceCommit,
) -> tuple[SemanticCounterClaim, ...]:
    return tuple(
        claim
        for claim in commit.counter_claims
        if claim.scope.kind is not SemanticCounterKind.NATURAL_DECISION_OCCURRENCE
    )


def _contains_advanced_claim(
    session: Session,
    commit: AuthoritativeTickSliceCommit,
    claims: tuple[SemanticCounterClaim, ...],
) -> bool:
    return any(_claim_is_advanced(_load_counter(session, commit, claim), claim) for claim in claims)


def _claim_is_advanced(
    counter: SemanticCounter | None, claim: SemanticCounterClaim
) -> bool:
    return counter is not None and counter.next_value >= claim.expected_next + claim.count


def _require_allocation_replay(
    session: Session,
    commit: AuthoritativeTickSliceCommit,
    claims: tuple[SemanticCounterClaim, ...],
) -> None:
    for claim in claims:
        if not _claim_is_advanced(_load_counter(session, commit, claim), claim):
            raise CounterClaimStaleError("advanced replay cannot mix a current allocation claim")


def _require_replayed_after_images(session: Session, state: ScrumStateWriteSet) -> None:
    for spec, items in zip(LOAD_SPECS[:9], state._collection_values()[:9], strict=True):
        model_type, value_type, _order = spec
        for item in items:
            model = session.get(
                model_type,
                _model_identity(item, model_type),
                populate_existing=True,
            )
            if model is None:
                raise CounterClaimStaleError("advanced replay references a missing after-image")
            if _domain_record(model, value_type) != item:
                raise ScrumStateConflictError("advanced replay changed a persisted after-image")


def _require_replayed_natural_claims(
    session: Session, commit: AuthoritativeTickSliceCommit
) -> None:
    for claim in commit.natural_decision_claims:
        eligibility, occurrence = _natural_rows(session, commit, claim)
        if eligibility is None or occurrence is None:
            raise CounterClaimStaleError("advanced replay cannot consume a natural occurrence")


def _require_immutable_fields(
    model: object, values: dict[str, object], model_type: type
) -> None:
    names = IMMUTABLE_AFTER_IMAGE_FIELDS.get(model_type, ())
    if any(getattr(model, name) != values[name] for name in names):
        raise ScrumStateConflictError("immutable Scrum fields have different content")


def _allocation_scope(item: object) -> SemanticCounterScope | None:
    if type(item) is SprintState:
        return SemanticCounterScope(SemanticCounterKind.SPRINT_ORDINAL, item.team_id, "SCRUM")
    if type(item) is WorkItemState:
        return SemanticCounterScope(
            SemanticCounterKind.ITEM_SEQUENCE,
            item.team_id,
            item.creation_kind.value,
        )
    if type(item) is StatusVisitState:
        return SemanticCounterScope(
            SemanticCounterKind.VISIT_ORDINAL,
            item.work_item_id,
            "VISIT",
        )
    return None


def _require_allocation_claim(
    item: object, commit: AuthoritativeTickSliceCommit
) -> None:
    scope = _allocation_scope(item)
    coordinate = _allocation_coordinate(item)
    claim = next((value for value in commit.counter_claims if value.scope == scope), None)
    if claim is None or not claim.expected_next <= coordinate < claim.expected_next + claim.count:
        raise CounterClaimStaleError("new allocated Scrum row has no matching counter claim")


def _allocation_coordinate(item: object) -> int:
    if type(item) is SprintState:
        return item.ordinal
    if type(item) is WorkItemState:
        return item.creation_sequence
    if type(item) is StatusVisitState:
        return item.ordinal
    raise TypeError("item is not an allocated Scrum row")


def _seed_owner_counters(
    session: Session,
    commit: AuthoritativeTickSliceCommit,
    owner_ids: tuple[set[UUID], set[UUID]],
) -> None:
    counters = (
        SemanticCounter(
            commit.live_slice.team_id,
            commit.live_slice.run_id,
            scope,
            0,
        )
        for scope in _owner_counter_scopes(owner_ids)
    )
    session.add_all(V2SemanticCounterModel(**_record_values(item)) for item in counters)
    session.flush()


def _owner_counter_scopes(
    owner_ids: tuple[set[UUID], set[UUID]],
) -> tuple[SemanticCounterScope, ...]:
    work_items, members = owner_ids
    work_scopes = tuple(
        scope
        for owner_id in sorted(work_items, key=str)
        for scope in (
            SemanticCounterScope(SemanticCounterKind.VISIT_ORDINAL, owner_id, "VISIT"),
            SemanticCounterScope(
                SemanticCounterKind.NATURAL_DECISION_OCCURRENCE,
                owner_id,
                DecisionType.RISK_CANCELLATION_OUTCOME.value,
            ),
        )
    )
    member_scopes = tuple(
        SemanticCounterScope(
            SemanticCounterKind.NATURAL_DECISION_OCCURRENCE,
            owner_id,
            DecisionType.RISK_MEMBER_UNAVAILABLE_OUTCOME.value,
        )
        for owner_id in sorted(members, key=str)
    )
    return (*work_scopes, *member_scopes)


def _model_identity(item: object, model_type: type) -> object:
    if model_type is V2MemberBusinessDateConsumptionModel:
        return (
            str(item.team_id),
            str(item.run_id),
            str(item.member_id),
            item.business_date,
        )
    if model_type is V2StatusVisitSampleModel:
        return str(item.visit_id)
    return str(item.id)


def _update_model(model: object, values: dict[str, object]) -> None:
    for field_name, value in values.items():
        setattr(model, field_name, value)


def _ordered_claims(
    claims: tuple[SemanticCounterClaim, ...],
) -> tuple[SemanticCounterClaim, ...]:
    return tuple(
        sorted(
            claims,
            key=lambda item: (
                item.scope.kind.value,
                str(item.scope.scope_id),
                item.scope.scope_key,
            ),
        )
    )


def _ordered_natural_claims(
    claims: tuple[EligibleNaturalDecisionClaim, ...],
) -> tuple[EligibleNaturalDecisionClaim, ...]:
    return tuple(
        sorted(
            claims,
            key=lambda item: (
                item.decision.decision_type.value,
                str(item.decision.entity_id),
                item.business_date,
            ),
        )
    )


def _preflight_natural_claims(
    session: Session, commit: AuthoritativeTickSliceCommit
) -> None:
    for claim in commit.natural_decision_claims:
        eligibility, occurrence = _natural_rows(session, commit, claim)
        if eligibility is not None and eligibility.occurrence != claim.decision.occurrence:
            raise NaturalClaimConflictError("eligibility already has a different occurrence")
        if occurrence is not None and occurrence.business_date != claim.business_date:
            raise NaturalClaimConflictError(
                "occurrence is already assigned to another business date"
            )


def _apply_counter_claim(
    session: Session,
    commit: AuthoritativeTickSliceCommit,
    claim: SemanticCounterClaim,
) -> SemanticCounter:
    current = _load_counter(session, commit, claim)
    if _natural_replay(session, commit, claim):
        return _require_advanced_counter(current, claim, False)
    if _advance_counter_row(session, commit, claim) == 1:
        return _require_counter(session, commit, claim)
    current = _require_counter(session, commit, claim)
    if claim.scope.kind is not SemanticCounterKind.NATURAL_DECISION_OCCURRENCE:
        inserted = claim.scope in session.info.get(NEW_ALLOCATION_SCOPES_KEY, ())
        return _require_advanced_counter(current, claim, inserted)
    raise CounterClaimStaleError("semantic counter compare-and-swap updated zero rows")


def _natural_replay(
    session: Session,
    commit: AuthoritativeTickSliceCommit,
    counter_claim: SemanticCounterClaim,
) -> bool:
    if counter_claim.scope.kind is not SemanticCounterKind.NATURAL_DECISION_OCCURRENCE:
        return False
    claim = next(
        item
        for item in commit.natural_decision_claims
        if _claim_scope(item) == counter_claim.scope
    )
    eligibility, _occurrence = _natural_rows(session, commit, claim)
    return eligibility is not None


def _require_advanced_counter(
    counter: SemanticCounter | None,
    claim: SemanticCounterClaim,
    newly_inserted: bool,
) -> SemanticCounter:
    expected = claim.expected_next + claim.count
    if newly_inserted or counter is None or counter.next_value < expected:
        raise CounterClaimStaleError("semantic counter does not match the claimed range")
    return counter


def _advance_counter_row(
    session: Session,
    commit: AuthoritativeTickSliceCommit,
    claim: SemanticCounterClaim,
) -> int:
    statement = (
        update(V2SemanticCounterModel)
        .where(*_counter_predicates(commit, claim))
        .where(V2SemanticCounterModel.next_value == claim.expected_next)
        .values(next_value=claim.expected_next + claim.count)
    )
    return session.execute(statement).rowcount


def _counter_predicates(
    commit: AuthoritativeTickSliceCommit, claim: SemanticCounterClaim
) -> tuple:
    scope = claim.scope
    return (
        V2SemanticCounterModel.team_id == str(commit.live_slice.team_id),
        V2SemanticCounterModel.run_id == str(commit.live_slice.run_id),
        V2SemanticCounterModel.kind == scope.kind.value,
        V2SemanticCounterModel.scope_id == str(scope.scope_id),
        V2SemanticCounterModel.scope_key == scope.scope_key,
    )


def _load_counter(
    session: Session,
    commit: AuthoritativeTickSliceCommit,
    claim: SemanticCounterClaim,
) -> SemanticCounter | None:
    statement = (
        select(V2SemanticCounterModel)
        .where(*_counter_predicates(commit, claim))
        .execution_options(populate_existing=True)
    )
    model = session.scalar(statement)
    return None if model is None else _domain_record(model, SemanticCounter)


def _require_counter(
    session: Session,
    commit: AuthoritativeTickSliceCommit,
    claim: SemanticCounterClaim,
) -> SemanticCounter:
    counter = _load_counter(session, commit, claim)
    if counter is None:
        raise CounterClaimStaleError("semantic counter row is missing")
    return counter


def _resolve_natural_claim(
    session: Session,
    commit: AuthoritativeTickSliceCommit,
    claim: EligibleNaturalDecisionClaim,
) -> NaturalDecisionEvaluation:
    eligibility, occurrence = _natural_rows(session, commit, claim)
    if eligibility is not None:
        if eligibility.occurrence != claim.decision.occurrence:
            raise NaturalClaimConflictError("eligibility has conflicting immutable content")
        return eligibility
    if occurrence is not None:
        raise NaturalClaimConflictError(
            "occurrence is already assigned to another eligibility"
        )
    return _insert_natural_claim(session, _evaluation_from_claim(commit, claim))


def _natural_rows(
    session: Session,
    commit: AuthoritativeTickSliceCommit,
    claim: EligibleNaturalDecisionClaim,
) -> tuple[NaturalDecisionEvaluation | None, NaturalDecisionEvaluation | None]:
    base = _natural_statement(commit, claim)
    eligibility = session.scalar(
        base.where(V2NaturalDecisionEvaluationModel.business_date == claim.business_date)
    )
    occurrence = session.scalar(
        base.where(V2NaturalDecisionEvaluationModel.occurrence == claim.decision.occurrence)
    )
    return _mapped_evaluation(eligibility), _mapped_evaluation(occurrence)


def _natural_statement(
    commit: AuthoritativeTickSliceCommit, claim: EligibleNaturalDecisionClaim
):
    decision = claim.decision
    return (
        select(V2NaturalDecisionEvaluationModel)
        .where(V2NaturalDecisionEvaluationModel.team_id == str(commit.live_slice.team_id))
        .where(V2NaturalDecisionEvaluationModel.run_id == str(commit.live_slice.run_id))
        .where(V2NaturalDecisionEvaluationModel.decision_type == decision.decision_type.value)
        .where(V2NaturalDecisionEvaluationModel.semantic_entity_id == str(decision.entity_id))
        .execution_options(populate_existing=True)
    )


def _mapped_evaluation(model: object | None) -> NaturalDecisionEvaluation | None:
    if model is None:
        return None
    try:
        return _domain_record(model, NaturalDecisionEvaluation)
    except (TypeError, ValueError) as error:
        raise NaturalClaimConflictError("stored natural eligibility is invalid") from error


def _evaluation_from_claim(
    commit: AuthoritativeTickSliceCommit, claim: EligibleNaturalDecisionClaim
) -> NaturalDecisionEvaluation:
    live = commit.live_slice
    decision = claim.decision
    path = (
        f"evaluation/{live.team_id}/{live.run_id}/{decision.decision_type.value}/"
        f"{decision.entity_id}/{claim.business_date}"
    )
    return NaturalDecisionEvaluation(
        semantic_uuid(path),
        live.team_id,
        live.run_id,
        decision.decision_type,
        decision.entity_id,
        claim.business_date,
        decision.occurrence,
        live.commit_id,
        live.recorded_at,
    )


def _insert_natural_claim(
    session: Session, evaluation: NaturalDecisionEvaluation
) -> NaturalDecisionEvaluation:
    model = V2NaturalDecisionEvaluationModel(**_record_values(evaluation))
    try:
        with session.begin_nested():
            session.add(model)
            session.flush()
    except IntegrityError as error:
        raise NaturalClaimConflictError("natural eligibility collided during insert") from error
    return evaluation


def _claim_scope(claim: EligibleNaturalDecisionClaim) -> SemanticCounterScope:
    return SemanticCounterScope(
        SemanticCounterKind.NATURAL_DECISION_OCCURRENCE,
        claim.decision.entity_id,
        claim.decision.decision_type.value,
    )


def _require_clean_session(session: Session) -> None:
    if session.new or session.dirty or session.deleted:
        raise ValueError("caller-owned Session must not contain pending ORM changes")


def _state_coordinates(state: ScrumStateWriteSet) -> tuple[UUID, UUID | None]:
    records = tuple(item for items in state._collection_values() for item in items)
    if not records:
        raise ValueError("Scrum state write set must not be empty")
    team_id = records[0].team_id
    run_id = next((item.run_id for item in records if hasattr(item, "run_id")), None)
    return team_id, run_id


def _candidate_snapshot(
    session: Session,
    state: ScrumStateWriteSet,
    coordinates: tuple[UUID, UUID | None],
) -> ScrumStateSnapshot:
    team_id, run_id = coordinates
    with session.no_autoflush:
        blueprint = _load_authority(session, team_id, run_id)
        current = _load_current_snapshot(session, coordinates, blueprint)
        candidate = _merged_snapshot(current, state)
        candidate.validate_against(blueprint)
    return candidate


def _load_current_snapshot(
    session: Session,
    coordinates: tuple[UUID, UUID | None],
    blueprint: ResolvedTeamBlueprint,
) -> ScrumStateSnapshot:
    team_id, run_id = coordinates
    if run_id is None:
        members = _load_team_members(session, team_id)
        snapshot = ScrumStateSnapshot(member_identities=members)
        snapshot.validate_against(blueprint)
        return snapshot
    query = ScrumStateQuery(team_id, run_id)
    return _load_validated_snapshot(session, query, blueprint)


def _load_validated_snapshot(
    session: Session,
    query: ScrumStateQuery,
    blueprint: ResolvedTeamBlueprint,
) -> ScrumStateSnapshot:
    collections = tuple(_load_collection(session, query, spec) for spec in LOAD_SPECS)
    snapshot = ScrumStateSnapshot(*collections)
    snapshot.validate_against(blueprint)
    return snapshot


def _load_team_members(session: Session, team_id: UUID) -> tuple[MemberIdentity, ...]:
    statement = select(V2MemberIdentityModel).where(
        V2MemberIdentityModel.team_id == str(team_id)
    )
    statement = statement.execution_options(populate_existing=True)
    models = session.scalars(statement.order_by(V2MemberIdentityModel.blueprint_index)).all()
    return tuple(_domain_record(model, MemberIdentity) for model in models)


def _load_authority(
    session: Session, team_id: UUID, run_id: UUID | None
) -> ResolvedTeamBlueprint:
    team = session.get(V2TeamModel, str(team_id), populate_existing=True)
    blueprint_row = session.scalar(
        select(V2TeamBlueprintModel)
        .where(V2TeamBlueprintModel.team_id == str(team_id))
        .execution_options(populate_existing=True)
    )
    if team is None or blueprint_row is None:
        raise ValueError("persisted team/run blueprint authority is incomplete")
    blueprint = _validated_blueprint(team, blueprint_row)
    if run_id is not None:
        _validate_run(session, team_id, run_id)
    return blueprint


def _validated_blueprint(
    team: V2TeamModel, row: V2TeamBlueprintModel
) -> ResolvedTeamBlueprint:
    blueprint = ResolvedTeamBlueprint.from_canonical_json(row.canonical_json)
    digest = canonical_sha256(json.loads(row.canonical_json))
    if row.sha256 != digest or team.blueprint_sha256 != digest:
        raise ValueError("persisted blueprint digest does not match its canonical document")
    if team.id != str(team_rng_id(digest)) or row.schema_version != blueprint.schema_version:
        raise ValueError("persisted team does not match its canonical blueprint")
    return blueprint


def _validate_run(session: Session, team_id: UUID, run_id: UUID) -> None:
    run = session.get(V2RunModel, str(run_id), populate_existing=True)
    if run is None or run.team_id != str(team_id):
        raise ValueError("persisted team/run ownership does not match")
    if run.id != str(run_rng_id(team_id, run.ordinal)):
        raise ValueError("persisted team/run semantic identity does not match")


def _apply_collection(session: Session, items: tuple[object, ...], model_type: type) -> None:
    if model_type is V2StatusVisitModel:
        _apply_visits(session, items)
        return
    models = [model_type(**_record_values(item)) for item in items]
    session.add_all(models)


def _apply_visits(session: Session, items: tuple[object, ...]) -> None:
    for item in items:
        values = _record_values(item)
        model = session.get(V2StatusVisitModel, values["id"], populate_existing=True)
        if model is None:
            _expunge_deleted_visit_identities(session, values["id"])
            session.add(V2StatusVisitModel(**values))
            continue
        for field_name, value in values.items():
            setattr(model, field_name, value)


def _expunge_deleted_visit_identities(session: Session, identity: object) -> None:
    for model_type in (V2StatusVisitModel, V2StatusVisitSampleModel):
        identity_key = session.identity_key(model_type, identity)
        stale = session.identity_map.get(identity_key)
        if stale is not None:
            session.expunge(stale)


def _merged_snapshot(
    current: ScrumStateSnapshot, touched: ScrumStateWriteSet
) -> ScrumStateSnapshot:
    collections = tuple(
        _merged_collection(existing, changes, spec[2])
        for spec, existing, changes in zip(
            LOAD_SPECS,
            current._collection_values(),
            touched._collection_values(),
            strict=True,
        )
    )
    return ScrumStateSnapshot(*collections)


def _merged_collection(
    existing: tuple[object, ...], changes: tuple[object, ...], order_names: tuple[str, ...]
) -> tuple[object, ...]:
    records = {_persistence_identity(record): record for record in existing}
    records.update({_persistence_identity(record): record for record in changes})
    return tuple(sorted(records.values(), key=lambda item: _semantic_order(item, order_names)))


def _persistence_identity(record: object) -> object:
    if type(record) is SemanticCounter:
        return record.team_id, record.run_id, record.scope
    if type(record) is MemberBusinessDateConsumption:
        return record.team_id, record.run_id, record.member_id, record.business_date
    return getattr(record, "id", getattr(record, "visit_id", None))


def _semantic_order(record: object, names: tuple[str, ...]) -> tuple[object, ...]:
    if type(record) is SemanticCounter:
        scope = record.scope
        return scope.kind.value, str(scope.scope_id), scope.scope_key
    return tuple(_sortable(getattr(record, name)) for name in names)


def _sortable(value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    return value


def _record_values(record: object) -> dict[str, object]:
    if type(record) is SemanticCounter:
        values = {
            "team_id": str(record.team_id),
            "run_id": str(record.run_id),
            "kind": record.scope.kind.value,
            "scope_id": str(record.scope.scope_id),
            "scope_key": record.scope.scope_key,
            "next_value": record.next_value,
        }
        return {**values, **_counter_owner_values(record)}
    if type(record) is NaturalDecisionEvaluation:
        values = {
            field.name: _stored_value(getattr(record, field.name))
            for field in fields(record)
        }
        return {**values, **_evaluation_owner_values(record)}
    return {field.name: _stored_value(getattr(record, field.name)) for field in fields(record)}


def _counter_owner_values(counter: SemanticCounter) -> dict[str, str | None]:
    scope = counter.scope
    if scope.kind is SemanticCounterKind.VISIT_ORDINAL:
        return {"work_item_id": str(scope.scope_id), "member_id": None}
    if scope.kind is SemanticCounterKind.NATURAL_DECISION_OCCURRENCE:
        if scope.scope_key == DecisionType.RISK_CANCELLATION_OUTCOME.value:
            return {"work_item_id": str(scope.scope_id), "member_id": None}
        return {"work_item_id": None, "member_id": str(scope.scope_id)}
    return {"work_item_id": None, "member_id": None}


def _evaluation_owner_values(
    evaluation: NaturalDecisionEvaluation,
) -> dict[str, str | None]:
    if evaluation.decision_type is DecisionType.RISK_CANCELLATION_OUTCOME:
        return {"work_item_id": str(evaluation.semantic_entity_id), "member_id": None}
    return {"work_item_id": None, "member_id": str(evaluation.semantic_entity_id)}


def _stored_value(value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    return value


def _load_collection(session: Session, query: ScrumStateQuery, spec: tuple) -> tuple:
    model_type, value_type, order_names = spec
    statement = select(model_type).where(model_type.team_id == str(query.team_id))
    if hasattr(model_type, "run_id"):
        statement = statement.where(model_type.run_id == str(query.run_id))
    statement = statement.execution_options(populate_existing=True)
    order_columns = tuple(getattr(model_type, name) for name in order_names)
    models = session.scalars(statement.order_by(*order_columns)).all()
    return tuple(_domain_record(model, value_type) for model in models)


def _domain_record(model: object, value_type: type) -> object:
    if value_type is SemanticCounter:
        scope = SemanticCounterScope(
            SemanticCounterKind(model.kind), UUID(model.scope_id), model.scope_key
        )
        return SemanticCounter(UUID(model.team_id), UUID(model.run_id), scope, model.next_value)
    values = {
        field.name: _domain_value(field.name, getattr(model, field.name), value_type)
        for field in fields(value_type)
    }
    if value_type is StatusVisitSample:
        return _raw_status_sample(values)
    return value_type(**values)


def _raw_status_sample(values: dict[str, object]) -> StatusVisitSample:
    sample = object.__new__(StatusVisitSample)
    for field_name, value in values.items():
        object.__setattr__(sample, field_name, value)
    sample.validate()
    return sample


def _domain_value(field_name: str, value: object, value_type: type) -> object:
    if value is None:
        return None
    enum_type = _enum_type(field_name, value_type)
    if enum_type is not None:
        return enum_type(value)
    if field_name == "story_points":
        return value
    if field_name.endswith("_id") or field_name == "id":
        return UUID(value)
    return value


def _enum_type(field_name: str, value_type: type) -> type[StrEnum] | None:
    if field_name != "lifecycle":
        return ENUM_FIELDS.get(field_name)
    lifecycle_types = (
        (WorkItemState, WorkItemLifecycle),
        (SprintState, SprintLifecycle),
        (StatusVisitState, StatusVisitLifecycle),
    )
    return next(
        (enum_type for domain_type, enum_type in lifecycle_types if value_type is domain_type), None
    )
