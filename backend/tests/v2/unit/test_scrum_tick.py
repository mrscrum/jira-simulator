"""Focused observable examples for one pragmatic incremental Scrum tick."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.v2.application.live_team import LiveTeamState
from app.v2.domain.canonical_json import canonical_json, canonical_sha256, semantic_uuid
from app.v2.domain.deterministic_rng import (
    CreationKind,
    DecisionOccurrence,
    DecisionType,
    DeterministicRandomStream,
    item_rng_id,
    member_rng_id,
    visit_rng_id,
)
from app.v2.domain.draw_source import SeededDrawSource
from app.v2.domain.sampling import sample_touch, touch_bounds
from app.v2.domain.scrum_state import (
    MemberBusinessDateConsumption,
    MemberIdentity,
    ScrumStateSnapshot,
    ScrumStateWriteSet,
    StatusVisitLifecycle,
    StatusVisitState,
    WorkItemLifecycle,
)
from app.v2.domain.scrum_tick import TickRequest, calculate_scrum_tick
from app.v2.domain.team_blueprint import AvailabilityInterval, Responsibility
from app.v2.domain.team_runtime import PersistedTeamAggregate, TeamRuntime, V2Run, V2Team
from tests.v2.scrum_state_support import (
    BLUEPRINT,
    BLUEPRINT_SHA256,
    MEMBER_ID,
    NOW,
    RUN_ID,
    TEAM_ID,
    make_member,
    make_sample_for,
    make_sprint,
    make_visit,
    make_work_item,
)

ONE_HOUR = timedelta(hours=1)
ONE_HOUR_MICROSECONDS = 3_600_000_000
DAY_START = datetime(2026, 8, 10, 16, tzinfo=UTC)


def test_tick_assigns_ranked_work_by_responsibility_proficiency_and_wip():
    senior_id = member_rng_id(TEAM_ID, 2)
    blueprint = _blueprint_with_senior_developer(max_concurrent_wip=1)
    first_work = make_work_item()
    first_visit = replace(make_visit(), member_id=None)
    second_work = replace(
        make_work_item(),
        id=item_rng_id(TEAM_ID, CreationKind.INITIAL_BACKLOG, 1),
        creation_sequence=1,
        relative_rank=3,
    )
    second_visit = _unowned_visit(second_work)
    state = _live_state(
        blueprint=blueprint,
        members=(MemberIdentity(senior_id, TEAM_ID, 2),),
        work_items=(first_work, second_work),
        visits=(first_visit, second_visit),
    )

    command = calculate_scrum_tick(
        state, _request(NOW + ONE_HOUR), SeededDrawSource(state.aggregate)
    )

    visits = {visit.work_item_id: visit for visit in command.state.status_visits}
    assert visits[first_work.id].member_id == senior_id
    assert visits[first_work.id].credited_labor_microseconds == 5_400_000_000
    assert visits[second_work.id].member_id is None
    assert visits[second_work.id].queue_microseconds == ONE_HOUR_MICROSECONDS
    assert _ground_truth(command, second_work.id)["reason"] == "WIP_LIMIT"


def test_tick_retains_an_eligible_owner_even_when_a_more_proficient_member_exists():
    senior_id = member_rng_id(TEAM_ID, 2)
    blueprint = _blueprint_with_senior_developer(max_concurrent_wip=2)
    state = _live_state(
        blueprint=blueprint,
        members=(make_member(), MemberIdentity(senior_id, TEAM_ID, 2)),
    )

    command = calculate_scrum_tick(
        state, _request(NOW + ONE_HOUR), SeededDrawSource(state.aggregate)
    )

    assert command.state.status_visits[0].member_id == MEMBER_ID
    assert _ground_truth(command)["reason"] == "PROGRESSED"


def test_tick_explains_queue_when_no_member_has_the_required_responsibility():
    developer = BLUEPRINT.members[1].model_copy(
        update={"responsibilities": (Responsibility(activity="analysis", proficiency=1.0),)}
    )
    blueprint = BLUEPRINT.model_copy(
        update={"members": (BLUEPRINT.members[0], developer)}
    )
    state = _live_state(blueprint=blueprint)

    command = calculate_scrum_tick(
        state, _request(NOW + ONE_HOUR), SeededDrawSource(state.aggregate)
    )

    assert _ground_truth(command)["reason"] == "NO_CAPABLE_MEMBER"


def test_tick_queues_work_while_the_owner_is_unavailable_under_a_runtime_overlay():
    provenance = {"source": "incident", "version": 1}
    overlay = replace(
        _overlay(),
        availability_fraction=0.0,
        daily_capacity_ceiling_microseconds=0,
        provenance_json=canonical_json(provenance),
        provenance_sha256=canonical_sha256(provenance),
    )
    state = _live_state(overlays=(overlay,))

    command = calculate_scrum_tick(
        state, _request(NOW + ONE_HOUR), SeededDrawSource(state.aggregate)
    )

    visit = command.state.status_visits[0]
    assert visit.member_id is None
    assert visit.elapsed_work_microseconds == make_visit().elapsed_work_microseconds
    assert visit.queue_microseconds == make_visit().queue_microseconds + ONE_HOUR_MICROSECONDS
    payload = _ground_truth(command)
    assert payload["reason"] == "UNAVAILABLE"
    assert payload["queue_delta_microseconds"] == ONE_HOUR_MICROSECONDS
    assert payload["remaining_before_microseconds"] == make_visit().remaining_work_microseconds
    assert payload["remaining_after_microseconds"] == make_visit().remaining_work_microseconds


def test_tick_stops_touch_when_daily_capacity_is_exhausted():
    consumption = MemberBusinessDateConsumption(
        TEAM_ID,
        RUN_ID,
        MEMBER_ID,
        datetime(2026, 8, 10, tzinfo=UTC).date(),
        6 * ONE_HOUR_MICROSECONDS,
    )
    state = _live_state(consumption=(consumption,))

    command = calculate_scrum_tick(
        state, _request(NOW + ONE_HOUR), SeededDrawSource(state.aggregate)
    )

    visit = command.state.status_visits[0]
    assert visit.elapsed_work_microseconds == make_visit().elapsed_work_microseconds
    assert visit.queue_microseconds == make_visit().queue_microseconds + ONE_HOUR_MICROSECONDS
    assert _ground_truth(command)["reason"] == "DAILY_CAPACITY"


def test_tick_uses_minimum_overlapping_availability_fraction_once():
    interval = _availability(DAY_START, DAY_START + timedelta(hours=2), 0.5, 6.0)
    blueprint = _blueprint_with_developer_availability((interval,))
    overlay = replace(
        _overlay(),
        starts_at=DAY_START,
        ends_at=DAY_START + timedelta(hours=2),
        availability_fraction=0.5,
        daily_capacity_ceiling_microseconds=6 * ONE_HOUR_MICROSECONDS,
    )
    visit = replace(make_visit(), entered_at=DAY_START)
    state = _with_runtime_start(
        _live_state(blueprint=blueprint, visits=(visit,), overlays=(overlay,)), DAY_START
    )

    command = calculate_scrum_tick(
        state,
        _request_for(state, DAY_START + timedelta(hours=2)),
        SeededDrawSource(state.aggregate),
    )

    assert (
        command.state.status_visits[0].credited_labor_microseconds
        - visit.credited_labor_microseconds
        == ONE_HOUR_MICROSECONDS
    )


def test_tick_applies_fraction_once_after_the_prefraction_daily_cap():
    interval = _availability(DAY_START, DAY_START + timedelta(hours=8), 0.5, 6.0)
    blueprint = _long_touch_blueprint(
        _blueprint_with_developer_availability((interval,))
    )
    visit = _long_visit(blueprint, DAY_START)
    state = _with_runtime_start(
        _live_state(blueprint=blueprint, visits=(visit,)), DAY_START
    )

    command = calculate_scrum_tick(
        state,
        _request_for(state, DAY_START + timedelta(hours=8)),
        SeededDrawSource(state.aggregate),
    )

    assert (
        command.state.status_visits[0].credited_labor_microseconds
        - visit.credited_labor_microseconds
        == 3 * ONE_HOUR_MICROSECONDS
    )


def test_tick_reallocates_at_configured_and_runtime_availability_boundaries():
    unavailable_first_hour = _availability(
        DAY_START, DAY_START + ONE_HOUR, 0.0, 6.0
    )
    backup_id = member_rng_id(TEAM_ID, 2)
    blueprint = _long_touch_blueprint(_blueprint_with_backup(unavailable_first_hour))
    backup_overlay = replace(
        _overlay(),
        id=semantic_uuid(f"overlay/{backup_id}/boundary"),
        member_id=backup_id,
        starts_at=DAY_START + ONE_HOUR,
        ends_at=DAY_START + timedelta(hours=2),
        availability_fraction=0.0,
        daily_capacity_ceiling_microseconds=0,
    )
    visit = _long_visit(blueprint, DAY_START)
    state = _with_runtime_start(
        _live_state(
            blueprint=blueprint,
            members=(make_member(), MemberIdentity(backup_id, TEAM_ID, 2)),
            visits=(visit,),
            overlays=(backup_overlay,),
        ),
        DAY_START,
    )

    command = calculate_scrum_tick(
        state,
        _request_for(state, DAY_START + timedelta(hours=2)),
        SeededDrawSource(state.aggregate),
    )

    consumption = {
        row.member_id: row.consumed_labor_microseconds
        for row in command.state.member_business_date_consumption
    }
    assert consumption == {
        MEMBER_ID: ONE_HOUR_MICROSECONDS,
        backup_id: ONE_HOUR_MICROSECONDS,
    }


def test_tick_shares_one_members_labor_across_concurrent_wip():
    first_work = make_work_item()
    first_visit = make_visit()
    second_work = replace(
        make_work_item(),
        id=item_rng_id(TEAM_ID, CreationKind.INITIAL_BACKLOG, 1),
        creation_sequence=1,
        relative_rank=3,
    )
    second_visit = replace(_unowned_visit(second_work), member_id=MEMBER_ID)
    state = _live_state(
        work_items=(first_work, second_work), visits=(first_visit, second_visit)
    )

    command = calculate_scrum_tick(
        state, _request(NOW + ONE_HOUR), SeededDrawSource(state.aggregate)
    )

    visits = {visit.work_item_id: visit for visit in command.state.status_visits}
    credited_delta = (
        visits[first_work.id].credited_labor_microseconds
        - first_visit.credited_labor_microseconds
        + visits[second_work.id].credited_labor_microseconds
        - second_visit.credited_labor_microseconds
    )
    assert credited_delta == ONE_HOUR_MICROSECONDS
    assert visits[second_work.id].queue_microseconds == ONE_HOUR_MICROSECONDS


def test_tick_keeps_visit_open_until_both_touch_and_sampled_dwell_are_complete():
    state = _live_state()

    command = calculate_scrum_tick(
        state, _request(NOW + timedelta(hours=3)), SeededDrawSource(state.aggregate)
    )

    visit = command.state.status_visits[0]
    assert visit.remaining_work_microseconds == 0
    assert visit.lifecycle is StatusVisitLifecycle.OPEN
    assert not command.state.work_items
    assert _ground_truth(command)["reason"] == "DWELLING"


def test_tick_completes_forward_route_without_fabricating_a_zero_touch_visit():
    state = _live_state()

    command = calculate_scrum_tick(
        state, _request(NOW + timedelta(hours=4, minutes=30)), SeededDrawSource(state.aggregate)
    )

    assert command.state.work_items[0].lifecycle is WorkItemLifecycle.DONE
    assert command.state.work_items[0].current_status_key == "DONE"
    assert len(command.state.status_visits) == 1
    assert command.state.status_visits[0].lifecycle is StatusVisitLifecycle.CLOSED
    assert not command.state.status_visit_samples
    assert not command.counter_claims
    assert len(command.live_slice.activity) == 1
    assert len(command.live_slice.ground_truth) == 1
    assert len(command.live_slice.projection_intents) == 1
    assert "moved to Done" in json.loads(
        command.live_slice.activity[0].canonical_payload
    )["summary"]
    payload = _ground_truth(command)
    assert payload["reason"] == "TRANSITIONED"
    assert payload["business_delta_microseconds"] < 4.5 * ONE_HOUR_MICROSECONDS
    assert payload["timing_context"]["dwell_sampled_hours"] > 0


def test_tick_stops_at_early_visit_completion_and_leaves_the_residual_interval():
    state = _live_state()
    requested_end = NOW + timedelta(hours=4, minutes=30)

    first = calculate_scrum_tick(
        state, _request(requested_end), SeededDrawSource(state.aggregate)
    )
    continued_state = _committed_state(state, first)
    second = calculate_scrum_tick(
        continued_state,
        _request_for(continued_state, requested_end),
        SeededDrawSource(continued_state.aggregate),
    )

    boundary = first.live_slice.runtime_after.simulation_time
    assert NOW < boundary < requested_end
    assert first.state.status_visits[0].closed_at == boundary
    assert second.live_slice.runtime_after.simulation_time == requested_end


def test_tick_is_deterministic_and_stops_at_the_visible_sprint_boundary():
    sprint = replace(make_sprint(), planned_end_at=NOW + timedelta(hours=4))
    state = _live_state(sprint=sprint)
    request = _request(NOW + timedelta(hours=8))

    first = calculate_scrum_tick(state, request, SeededDrawSource(state.aggregate))
    second = calculate_scrum_tick(state, request, SeededDrawSource(state.aggregate))

    assert first == second
    assert first.live_slice.runtime_after.simulation_time == sprint.planned_end_at
    assert first.live_slice.runtime_after.next_wake_at == sprint.planned_end_at


def _request(ends_at: datetime) -> TickRequest:
    return TickRequest(TEAM_ID, ends_at, ends_at)


def _request_for(state: LiveTeamState, ends_at: datetime) -> TickRequest:
    return TickRequest(state.aggregate.team.id, ends_at, ends_at)


def _live_state(
    *,
    blueprint=BLUEPRINT,
    members: tuple[MemberIdentity, ...] | None = None,
    work_items=None,
    visits=None,
    overlays=(),
    consumption=(),
    sprint=None,
) -> LiveTeamState:
    selected_members = members if members is not None else (make_member(),)
    selected_work = work_items if work_items is not None else (make_work_item(),)
    selected_visits = visits if visits is not None else (make_visit(),)
    samples = tuple(
        make_sample_for(blueprint, work, visit)
        for work, visit in zip(selected_work, selected_visits, strict=True)
    )
    write_set = ScrumStateWriteSet(
        member_identities=selected_members,
        member_availability_overlays=overlays,
        member_business_date_consumption=consumption,
        work_items=selected_work,
        sprints=(sprint if sprint is not None else make_sprint(),),
        status_visits=selected_visits,
        status_visit_samples=samples,
    )
    return LiveTeamState(_aggregate(blueprint), ScrumStateSnapshot.from_write_set(write_set))


def _aggregate(blueprint) -> PersistedTeamAggregate:
    team = V2Team(TEAM_ID, "tick-unit", BLUEPRINT_SHA256, "Tick Team", "SCRUM", NOW)
    run = V2Run(RUN_ID, TEAM_ID, 0, "ACTIVE", NOW)
    runtime = TeamRuntime(
        semantic_uuid(f"runtime/{TEAM_ID}"),
        TEAM_ID,
        RUN_ID,
        0,
        "RUNNING",
        NOW,
        NOW,
        NOW,
        NOW,
    )
    return PersistedTeamAggregate(
        team,
        semantic_uuid(f"blueprint/{TEAM_ID}/{BLUEPRINT_SHA256}"),
        blueprint,
        BLUEPRINT_SHA256,
        NOW,
        run,
        runtime,
    )


def _blueprint_with_senior_developer(max_concurrent_wip: int):
    developer = BLUEPRINT.members[1]
    senior = developer.model_copy(
        update={
            "name": "Senior Developer",
            "max_concurrent_wip": max_concurrent_wip,
            "responsibilities": (Responsibility(activity="development", proficiency=2.0),),
            "availability": (),
        }
    )
    return BLUEPRINT.model_copy(update={"members": (*BLUEPRINT.members, senior)})


def _unowned_visit(work_item) -> StatusVisitState:
    source = make_visit()
    visit_id = visit_rng_id(work_item.id, 0)
    stream = DeterministicRandomStream(BLUEPRINT.seed, TEAM_ID, RUN_ID)
    draw = stream.draw(DecisionOccurrence(visit_id, DecisionType.STATUS_TOUCH, 0))
    entry = next(
        item
        for item in BLUEPRINT.timing.entries
        if (item.status_key, item.issue_type, item.story_points)
        == ("DEVELOPMENT", work_item.issue_type, work_item.story_points)
    )
    required = round(
        sample_touch(touch_bounds(entry), draw.unit_value).sampled_hours
        * ONE_HOUR_MICROSECONDS
    )
    visit = replace(
        source,
        id=visit_id,
        work_item_id=work_item.id,
        member_id=None,
        required_work_microseconds=required,
        elapsed_work_microseconds=0,
        remaining_work_microseconds=required,
        queue_microseconds=0,
        credited_labor_microseconds=0,
    )
    return visit


def _overlay():
    from tests.v2.scrum_state_support import make_overlay

    return make_overlay()


def _availability(
    starts_at: datetime,
    ends_at: datetime,
    fraction: float,
    daily_capacity_hours: float,
) -> AvailabilityInterval:
    return AvailabilityInterval(
        starts_at=starts_at,
        ends_at=ends_at,
        availability_fraction=fraction,
        daily_capacity_hours_override=daily_capacity_hours,
        reason="review fixture",
    )


def _blueprint_with_developer_availability(intervals):
    developer = BLUEPRINT.members[1].model_copy(update={"availability": intervals})
    return BLUEPRINT.model_copy(
        update={"members": (BLUEPRINT.members[0], developer)}
    )


def _blueprint_with_backup(primary_interval):
    primary = BLUEPRINT.members[1].model_copy(update={"availability": (primary_interval,)})
    backup = BLUEPRINT.members[1].model_copy(
        update={"name": "Backup Developer", "availability": ()}
    )
    return BLUEPRINT.model_copy(
        update={"members": (BLUEPRINT.members[0], primary, backup)}
    )


def _long_touch_blueprint(blueprint):
    entries = tuple(
        entry.model_copy(update={"touch_min": 10.0, "touch_max": 10.0})
        if (entry.status_key, entry.issue_type, entry.story_points)
        == ("DEVELOPMENT", "STORY", 3)
        else entry
        for entry in blueprint.timing.entries
    )
    return blueprint.model_copy(
        update={"timing": blueprint.timing.model_copy(update={"entries": entries})}
    )


def _long_visit(blueprint, entered_at):
    source = make_visit()
    stream = DeterministicRandomStream(blueprint.seed, TEAM_ID, RUN_ID)
    draw = stream.draw(DecisionOccurrence(source.id, DecisionType.STATUS_TOUCH, 0))
    entry = next(
        item
        for item in blueprint.timing.entries
        if (item.status_key, item.issue_type, item.story_points)
        == ("DEVELOPMENT", "STORY", 3)
    )
    required = round(
        sample_touch(touch_bounds(entry), draw.unit_value).sampled_hours
        * ONE_HOUR_MICROSECONDS
    )
    return replace(
        source,
        entered_at=entered_at,
        required_work_microseconds=required,
        elapsed_work_microseconds=0,
        remaining_work_microseconds=required,
        queue_microseconds=0,
        credited_labor_microseconds=0,
    )


def _with_runtime_start(state: LiveTeamState, starts_at: datetime) -> LiveTeamState:
    runtime = replace(
        state.aggregate.runtime,
        simulation_time=starts_at,
        next_wake_at=starts_at,
        updated_at=starts_at,
    )
    return replace(state, aggregate=replace(state.aggregate, runtime=runtime))


def _ground_truth(command, work_item_id=None):
    records = command.live_slice.ground_truth
    if work_item_id is not None:
        record = next(
            item
            for item in records
            if json.loads(item.canonical_payload)["work_item_id"] == str(work_item_id)
        )
    else:
        record = records[0]
    return json.loads(record.canonical_payload)


def _committed_state(state: LiveTeamState, command) -> LiveTeamState:
    scrum = state.scrum
    values = {}
    for field_name in scrum.__dataclass_fields__:
        existing = getattr(scrum, field_name)
        touched = getattr(command.state, field_name)
        records = {_identity(item): item for item in existing}
        records.update({_identity(item): item for item in touched})
        values[field_name] = tuple(records.values())
    snapshot = ScrumStateSnapshot(**values)
    runtime_after = command.live_slice.runtime_after
    runtime = replace(
        state.aggregate.runtime,
        version=state.aggregate.runtime.version + 1,
        state=runtime_after.state,
        simulation_time=runtime_after.simulation_time,
        next_wake_at=runtime_after.next_wake_at,
        updated_at=command.live_slice.recorded_at,
    )
    return LiveTeamState(replace(state.aggregate, runtime=runtime), snapshot)


def _identity(item):
    if isinstance(item, MemberBusinessDateConsumption):
        return item.member_id, item.business_date
    return getattr(item, "id", getattr(item, "visit_id", None))
