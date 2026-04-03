"""API router for scheduled events, audit, and precomputation."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.models.scheduled_event import ScheduledEvent
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
