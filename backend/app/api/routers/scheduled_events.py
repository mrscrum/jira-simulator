"""API router for scheduled events, audit, and precomputation."""

from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.issue import Issue
from app.models.scheduled_event import ScheduledEvent
from app.models.sprint import Sprint
from app.schemas.scheduled_event import (
    AuditSummary,
    EventAuditRead,
    PrecomputeRequest,
    PrecomputeResponse,
    ScheduledEventCancel,
    ScheduledEventListResponse,
    ScheduledEventRead,
    ScheduledEventUpdate,
)

router = APIRouter(tags=["scheduled-events"])


# ── List events for a sprint ──────────────────────────────────────────────

@router.get(
    "/teams/{team_id}/sprints/{sprint_id}/events",
    response_model=ScheduledEventListResponse,
)
def list_scheduled_events(
    team_id: int,
    sprint_id: int,
    request: Request,
    status: str | None = Query(None, description="Filter by status"),
    event_type: str | None = Query(None, description="Filter by event type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    session: Session = request.app.state.session_factory()
    try:
        query = session.query(ScheduledEvent).filter_by(
            team_id=team_id, sprint_id=sprint_id,
        )
        if status:
            query = query.filter(ScheduledEvent.status == status)
        if event_type:
            query = query.filter(ScheduledEvent.event_type == event_type)

        total = query.count()
        events = (
            query
            .order_by(ScheduledEvent.scheduled_at, ScheduledEvent.sequence_order)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return ScheduledEventListResponse(
            events=[ScheduledEventRead.model_validate(e) for e in events],
            total=total,
            page=page,
            page_size=page_size,
        )
    finally:
        session.close()


# ── Get single event ──────────────────────────────────────────────────────

@router.get(
    "/scheduled-events/{event_id}",
    response_model=ScheduledEventRead,
)
def get_scheduled_event(event_id: int, request: Request):
    session: Session = request.app.state.session_factory()
    try:
        event = session.get(ScheduledEvent, event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")
        return ScheduledEventRead.model_validate(event)
    finally:
        session.close()


# ── Cancel single event ──────────────────────────────────────────────────

@router.post(
    "/scheduled-events/{event_id}/cancel",
)
def cancel_scheduled_event(
    event_id: int,
    body: ScheduledEventCancel,
    request: Request,
):
    """Delete a single pending event."""
    session: Session = request.app.state.session_factory()
    try:
        event = session.get(ScheduledEvent, event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")
        if event.status not in ("PENDING", "MODIFIED"):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel event in {event.status} status",
            )

        session.delete(event)
        session.commit()

        return {"deleted": True, "id": event_id}
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Modify event (time and/or payload) ───────────────────────────────────

@router.patch(
    "/scheduled-events/{event_id}",
    response_model=ScheduledEventRead,
)
def modify_scheduled_event(
    event_id: int,
    body: ScheduledEventUpdate,
    request: Request,
):
    session: Session = request.app.state.session_factory()
    try:
        event = session.get(ScheduledEvent, event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")
        if event.status != "PENDING":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot modify event in {event.status} status",
            )

        now = datetime.now(UTC)

        if body.scheduled_at is not None:
            if event.original_scheduled_at is None:
                event.original_scheduled_at = event.scheduled_at
            event.scheduled_at = body.scheduled_at

        if body.payload is not None:
            if event.original_payload is None:
                event.original_payload = event.payload
            event.payload = body.payload

        event.modified_at = now
        event.status = "MODIFIED"
        session.commit()

        return ScheduledEventRead.model_validate(event)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Cancel all pending events for a sprint ────────────────────────────────

@router.post(
    "/teams/{team_id}/sprints/{sprint_id}/events/cancel-all",
)
def cancel_all_pending_events(
    team_id: int,
    sprint_id: int,
    request: Request,
):
    """Delete all pending/modified events for a sprint."""
    session: Session = request.app.state.session_factory()
    try:
        count = (
            session.query(ScheduledEvent)
            .filter_by(team_id=team_id, sprint_id=sprint_id)
            .filter(ScheduledEvent.status.in_(["PENDING", "MODIFIED"]))
            .delete(synchronize_session="fetch")
        )

        session.commit()
        return {"deleted": count}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Trigger precomputation ────────────────────────────────────────────────

@router.post(
    "/teams/{team_id}/sprints/precompute",
    response_model=PrecomputeResponse,
)
async def trigger_precomputation(
    team_id: int,
    body: PrecomputeRequest,
    request: Request,
):
    engine = request.app.state.simulation_engine
    result = await engine.compute_and_schedule_sprint(
        team_id=team_id,
        rng_seed=body.rng_seed,
    )
    return PrecomputeResponse(**result)


# ── Re-compute sprint (cancel old + recompute) ───────────────────────────

@router.post(
    "/teams/{team_id}/sprints/{sprint_id}/recompute",
    response_model=PrecomputeResponse,
)
async def recompute_sprint(
    team_id: int,
    sprint_id: int,
    body: PrecomputeRequest,
    request: Request,
):
    """Delete old pending events and recompute for the same sprint."""
    engine = request.app.state.simulation_engine
    result = await engine.recompute_sprint_schedule(
        team_id=team_id,
        sprint_id=sprint_id,
        rng_seed=body.rng_seed,
    )
    return PrecomputeResponse(**result)


# ── Manual dispatch trigger ───────────────────────────────────────────────

@router.post("/simulation/dispatch")
def trigger_dispatch(request: Request):
    dispatcher = request.app.state.event_dispatcher
    count = dispatcher.dispatch_due_events()
    return {"dispatched": count}


# ── Audit summary ─────────────────────────────────────────────────────────

@router.get(
    "/teams/{team_id}/sprints/{sprint_id}/audit",
    response_model=AuditSummary,
)
async def get_audit_summary(
    team_id: int,
    sprint_id: int,
    request: Request,
):
    auditor = request.app.state.event_auditor
    summary = await auditor.get_audit_summary(team_id, sprint_id)
    failures = [
        EventAuditRead.model_validate(f) for f in summary.pop("failures", [])
    ]
    return AuditSummary(**summary, failures=failures)


# ── Sprint items (per-item view) ─────────────────────────────────────────

@router.get("/teams/{team_id}/sprints/{sprint_id}/items")
def list_sprint_items(
    team_id: int,
    sprint_id: int,
    request: Request,
):
    """List all issues in a sprint with their event counts."""
    session: Session = request.app.state.session_factory()
    try:
        issues = (
            session.query(Issue)
            .filter_by(team_id=team_id, sprint_id=sprint_id)
            .order_by(Issue.backlog_priority.asc())
            .all()
        )

        # Count events per issue
        event_counts = dict(
            session.query(
                ScheduledEvent.issue_id,
                func.count(ScheduledEvent.id),
            )
            .filter_by(team_id=team_id, sprint_id=sprint_id)
            .filter(ScheduledEvent.issue_id.isnot(None))
            .group_by(ScheduledEvent.issue_id)
            .all()
        )

        return [
            {
                "id": i.id,
                "jira_issue_key": i.jira_issue_key,
                "summary": i.summary,
                "issue_type": i.issue_type,
                "story_points": i.story_points,
                "status": i.status,
                "completed_at": (
                    i.completed_at.isoformat() if i.completed_at else None
                ),
                "event_count": event_counts.get(i.id, 0),
            }
            for i in issues
        ]
    finally:
        session.close()


@router.get(
    "/teams/{team_id}/sprints/{sprint_id}/items/{issue_id}/events",
)
def list_item_events(
    team_id: int,
    sprint_id: int,
    issue_id: int,
    request: Request,
):
    """List all scheduled events for a specific issue in a sprint."""
    session: Session = request.app.state.session_factory()
    try:
        events = (
            session.query(ScheduledEvent)
            .filter_by(
                team_id=team_id,
                sprint_id=sprint_id,
                issue_id=issue_id,
            )
            .order_by(
                ScheduledEvent.scheduled_at,
                ScheduledEvent.sequence_order,
            )
            .all()
        )
        return [
            ScheduledEventRead.model_validate(e) for e in events
        ]
    finally:
        session.close()


# ── Flow matrix ──────────────────────────────────────────────────────────

@router.get("/teams/{team_id}/sprints/{sprint_id}/flow-matrix")
def get_flow_matrix(
    team_id: int,
    sprint_id: int,
    request: Request,
):
    """Build a status × day flow matrix from scheduled events.

    Walks through TRANSITION_ISSUE events in order, tracks each
    issue's status at end-of-day boundaries, returns item counts
    and story-point sums per (status, day).
    """
    session: Session = request.app.state.session_factory()
    try:
        sprint = session.get(Sprint, sprint_id)
        if sprint is None:
            raise HTTPException(
                status_code=404, detail="Sprint not found",
            )

        # Load all sprint issues for initial state
        issues = (
            session.query(Issue)
            .filter_by(team_id=team_id, sprint_id=sprint_id)
            .all()
        )
        if not issues:
            return {"days": [], "statuses": [], "items": [], "points": []}

        # Issue id → (current_status, story_points)
        issue_state: dict[int, str] = {}
        issue_points: dict[int, int] = {}
        for issue in issues:
            issue_state[issue.id] = "Backlog"
            issue_points[issue.id] = issue.story_points or 0

        # Load transition events ordered by time
        events = (
            session.query(ScheduledEvent)
            .filter_by(team_id=team_id, sprint_id=sprint_id)
            .filter(
                ScheduledEvent.event_type == "TRANSITION_ISSUE",
            )
            .order_by(
                ScheduledEvent.scheduled_at,
                ScheduledEvent.sequence_order,
            )
            .all()
        )

        if not events:
            return {"days": [], "statuses": [], "items": [], "points": []}

        # Normalize datetimes: ensure all are naive (strip tzinfo)
        # PostgreSQL DateTime columns return naive datetimes
        def _naive(dt: datetime) -> datetime:
            """Strip timezone info for consistent comparison."""
            if dt.tzinfo is not None:
                return dt.replace(tzinfo=None)
            return dt

        # Determine day boundaries from sprint dates
        sprint_start = _naive(sprint.start_date)
        sprint_end = _naive(sprint.end_date)

        # Use the actual event time range (not just sprint dates)
        # to ensure we cover all days with events
        first_event_date = _naive(events[0].scheduled_at).date()
        last_event_date = _naive(events[-1].scheduled_at).date()
        start_date = min(sprint_start.date(), first_event_date)
        end_date = max(sprint_end.date(), last_event_date)

        from datetime import timedelta
        days: list[str] = []
        day_boundaries: list[datetime] = []
        current_day = start_date
        while current_day <= end_date:
            days.append(current_day.strftime("%b %d"))
            # End of day = start of next day (naive)
            next_day = current_day + timedelta(days=1)
            day_boundaries.append(
                datetime(
                    next_day.year, next_day.month, next_day.day,
                ),
            )
            current_day = next_day

        # Walk events and snapshot status at each day boundary
        event_idx = 0
        all_statuses: set[str] = set()

        # day_index → {status → (item_count, point_sum)}
        matrix: dict[int, dict[str, list[int]]] = {}

        for day_idx, boundary in enumerate(day_boundaries):
            # Apply all events before this boundary
            while (
                event_idx < len(events)
                and _naive(events[event_idx].scheduled_at) < boundary
            ):
                ev = events[event_idx]
                target = ev.payload.get("target_status")
                if target and ev.issue_id:
                    issue_state[ev.issue_id] = target
                event_idx += 1

            # Snapshot: count items per status
            status_counts: dict[str, list[int]] = defaultdict(
                lambda: [0, 0],
            )
            for iid, status in issue_state.items():
                status_counts[status][0] += 1
                status_counts[status][1] += issue_points.get(iid, 0)
                all_statuses.add(status)

            matrix[day_idx] = dict(status_counts)

        # Build response in order
        ordered_statuses = sorted(all_statuses)
        items_grid = []
        points_grid = []
        for status in ordered_statuses:
            item_row = []
            point_row = []
            for day_idx in range(len(days)):
                cell = matrix.get(day_idx, {}).get(status, [0, 0])
                item_row.append(cell[0])
                point_row.append(cell[1])
            items_grid.append(item_row)
            points_grid.append(point_row)

        return {
            "days": days,
            "statuses": ordered_statuses,
            "items": items_grid,
            "points": points_grid,
        }
    finally:
        session.close()


# ── Diagnostics ─────────────────────────────────────────────────────────

@router.get("/teams/{team_id}/sprints/{sprint_id}/diagnostics")
def sprint_diagnostics(
    team_id: int,
    sprint_id: int,
    request: Request,
):
    """Diagnostic info about a sprint's precomputed events."""
    from collections import Counter

    from app.models.member import Member
    from app.models.touch_time_config import TouchTimeConfig
    from app.models.workflow import Workflow
    from app.models.workflow_step import WorkflowStep

    session: Session = request.app.state.session_factory()
    try:
        sprint = session.get(Sprint, sprint_id)
        if sprint is None:
            raise HTTPException(status_code=404, detail="Sprint not found")

        # Event stats
        events = (
            session.query(ScheduledEvent)
            .filter_by(team_id=team_id, sprint_id=sprint_id)
            .all()
        )
        tick_counts = Counter(e.sim_tick for e in events)
        type_counts = Counter(e.event_type for e in events)
        status_counts = Counter(e.status for e in events)

        # Issues in sprint
        issues = (
            session.query(Issue)
            .filter_by(team_id=team_id, sprint_id=sprint_id)
            .all()
        )
        issue_types = Counter(i.issue_type for i in issues)
        sp_values = Counter(i.story_points for i in issues)

        # Workflow + TTCs
        workflow = (
            session.query(Workflow)
            .filter_by(team_id=team_id).first()
        )
        step_info = []
        ttc_count = 0
        if workflow:
            steps = (
                session.query(WorkflowStep)
                .filter_by(workflow_id=workflow.id)
                .order_by(WorkflowStep.order)
                .all()
            )
            step_ids = [s.id for s in steps]
            ttc_count = (
                session.query(TouchTimeConfig)
                .filter(TouchTimeConfig.workflow_step_id.in_(step_ids))
                .count()
            )
            for s in steps:
                step_ttcs = (
                    session.query(TouchTimeConfig)
                    .filter_by(workflow_step_id=s.id)
                    .all()
                )
                step_info.append({
                    "id": s.id,
                    "status": s.jira_status,
                    "order": s.order,
                    "role_required": s.role_required,
                    "ttc_count": len(step_ttcs),
                    "ttc_issue_types": list(
                        {t.issue_type for t in step_ttcs},
                    ),
                    "ttc_story_points": sorted(
                        {t.story_points for t in step_ttcs},
                    ),
                })

        # Members
        members = (
            session.query(Member)
            .filter_by(team_id=team_id, is_active=True)
            .all()
        )
        member_roles = Counter(m.role for m in members)

        from app.models.team import Team
        team = session.get(Team, team_id)

        return {
            "sprint": {
                "id": sprint.id,
                "name": sprint.name,
                "phase": sprint.phase,
                "start_date": (
                    sprint.start_date.isoformat()
                    if sprint.start_date else None
                ),
                "end_date": (
                    sprint.end_date.isoformat()
                    if sprint.end_date else None
                ),
                "committed_points": sprint.committed_points,
            },
            "team": {
                "sprint_length_days": (
                    team.sprint_length_days if team else None
                ),
                "tick_duration_hours": (
                    team.tick_duration_hours if team else None
                ),
                "working_hours": (
                    f"{team.working_hours_start}-{team.working_hours_end}"
                    if team else None
                ),
                "timezone": team.timezone if team else None,
            },
            "events": {
                "total": len(events),
                "by_tick": dict(sorted(tick_counts.items())),
                "by_type": dict(type_counts),
                "by_status": dict(status_counts),
            },
            "issues": {
                "count": len(issues),
                "by_type": dict(issue_types),
                "by_story_points": dict(sp_values),
            },
            "workflow": {
                "steps": step_info,
                "total_ttcs": ttc_count,
            },
            "members": {
                "count": len(members),
                "by_role": dict(member_roles),
            },
        }
    finally:
        session.close()
