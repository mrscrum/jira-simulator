"""Simulation control API — wires engine, sprint, event, and backlog endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.engine.simulation import SimulationEngine

router = APIRouter(tags=["simulation"])


# ── Pydantic schemas ──


class SimulationStatus(BaseModel):
    status: str
    tick_count: int = 0
    last_successful_tick: str | None = None


class TickInterval(BaseModel):
    minutes: int


class InjectRequest(BaseModel):
    team_id: int
    dysfunction_type: str
    target_issue_id: int | None = None
    target_member_id: int | None = None


class InjectResponse(BaseModel):
    injected: bool


class BacklogGenerateRequest(BaseModel):
    count: int = 10


class EventConfigUpdate(BaseModel):
    enabled: bool | None = None
    probability: float | None = None
    params: dict | None = None


class ClockSpeed(BaseModel):
    speed: float


class EngineHealth(BaseModel):
    state: str
    tick_count: int
    last_successful_tick: str | None
    paused_teams: list[int]


# ── Helpers ──


def _get_engine(request: Request) -> SimulationEngine:
    engine = getattr(request.app.state, "simulation_engine", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="Simulation engine not initialised")
    return engine


def _resume_scheduler_jobs(request: Request) -> None:
    """Resume the simulation tick + queue scheduler jobs."""
    from datetime import UTC, datetime

    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None:
        return
    for job_id in ("simulation_tick", "queue_process"):
        job = scheduler.get_job(job_id)
        if job:
            job.resume()
            # Ensure next_run_time is set so the job actually fires.
            if job.next_run_time is None:
                job.modify(next_run_time=datetime.now(UTC))


def _pause_scheduler_jobs(request: Request) -> None:
    """Pause the simulation tick + queue scheduler jobs."""
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None:
        return
    for job_id in ("simulation_tick", "queue_process"):
        job = scheduler.get_job(job_id)
        if job:
            job.pause()


# ── Global simulation control ──


@router.get("/simulation/status", response_model=SimulationStatus)
def get_status(request: Request):
    engine = _get_engine(request)
    return SimulationStatus(
        status=engine.state.value.lower(),
        tick_count=engine.tick_count,
        last_successful_tick=(
            engine.last_successful_tick.isoformat()
            if engine.last_successful_tick
            else None
        ),
    )


@router.post("/simulation/start", response_model=SimulationStatus)
def start(request: Request):
    engine = _get_engine(request)
    engine.start()
    _resume_scheduler_jobs(request)
    return SimulationStatus(status="running", tick_count=engine.tick_count)


@router.post("/simulation/pause", response_model=SimulationStatus)
def pause(request: Request):
    engine = _get_engine(request)
    engine.pause()
    _pause_scheduler_jobs(request)
    return SimulationStatus(status="paused", tick_count=engine.tick_count)


@router.post("/simulation/resume", response_model=SimulationStatus)
def resume(request: Request):
    engine = _get_engine(request)
    engine.resume()
    _resume_scheduler_jobs(request)
    return SimulationStatus(status="running", tick_count=engine.tick_count)


@router.post("/simulation/reset", response_model=SimulationStatus)
def reset(request: Request):
    engine = _get_engine(request)
    engine.stop()
    _pause_scheduler_jobs(request)
    return SimulationStatus(status="stopped", tick_count=0)


@router.post("/simulation/tick")
async def manual_tick(request: Request):
    """Trigger a single simulation tick manually (for testing)."""
    engine = _get_engine(request)
    if not engine.should_tick():
        engine.start()
    results = await engine.tick()

    # Process the Jira write queue after the tick.
    write_queue = getattr(request.app.state, "write_queue", None)
    queue_result = None
    if write_queue:
        try:
            await write_queue.process_batch(tick_interval_seconds=10)
            queue_result = "processed"
        except Exception as e:
            queue_result = f"error: {e}"

    return {
        "tick_count": engine.tick_count,
        "queue": queue_result,
        "teams": [
            {
                "team_id": r.team_id,
                "jira_actions": r.jira_actions_count,
                "events": r.events_fired,
                "error": r.error,
            }
            for r in results
        ],
    }


@router.put("/simulation/tick-interval", response_model=TickInterval)
def update_tick_interval(body: TickInterval, request: Request):
    # Store on engine for scheduler to read
    engine = _get_engine(request)
    engine.tick_interval_minutes = body.minutes
    return body


@router.get("/simulation/clock", response_model=ClockSpeed)
def get_clock(request: Request):
    engine = _get_engine(request)
    return ClockSpeed(speed=engine.clock.speed)


@router.put("/simulation/clock", response_model=ClockSpeed)
def set_clock(body: ClockSpeed, request: Request):
    """Set simulation clock speed. 1.0 = real time, 60.0 = 1 min real = 1 hr sim."""
    engine = _get_engine(request)
    engine.clock.speed = body.speed
    return ClockSpeed(speed=engine.clock.speed)


# ── Per-team simulation control ──


@router.post("/simulation/{team_id}/start", response_model=SimulationStatus)
def start_team(team_id: int, request: Request):
    engine = _get_engine(request)
    engine.resume_team(team_id)
    return SimulationStatus(status="running", tick_count=engine.tick_count)


@router.post("/simulation/{team_id}/pause", response_model=SimulationStatus)
def pause_team(team_id: int, request: Request):
    engine = _get_engine(request)
    engine.pause_team(team_id)
    return SimulationStatus(status="paused", tick_count=engine.tick_count)


@router.post("/simulation/{team_id}/resume", response_model=SimulationStatus)
def resume_team(team_id: int, request: Request):
    engine = _get_engine(request)
    engine.resume_team(team_id)
    return SimulationStatus(status="running", tick_count=engine.tick_count)


# ── Sprint control ──


@router.get("/simulation/{team_id}/sprint/current")
def get_current_sprint(team_id: int, db: Session = Depends(get_session)):
    from app.models.sprint import Sprint
    sprint = (
        db.query(Sprint)
        .filter(Sprint.team_id == team_id)
        .order_by(Sprint.id.desc())
        .first()
    )
    if not sprint:
        raise HTTPException(status_code=404, detail="No sprint found")
    return {
        "id": sprint.id,
        "name": sprint.name,
        "status": sprint.status,
        "phase": sprint.phase,
        "sprint_number": sprint.sprint_number,
        "committed_points": sprint.committed_points,
        "completed_points": sprint.completed_points,
        "carried_over_points": sprint.carried_over_points,
        "velocity": sprint.velocity,
        "goal_at_risk": sprint.goal_at_risk,
    }


@router.post("/simulation/{team_id}/sprint/advance")
def advance_sprint(team_id: int, db: Session = Depends(get_session)):
    from app.models.sprint import Sprint
    sprint = (
        db.query(Sprint)
        .filter(Sprint.team_id == team_id)
        .order_by(Sprint.id.desc())
        .first()
    )
    if not sprint:
        raise HTTPException(status_code=404, detail="No sprint found")
    return {"id": sprint.id, "phase": sprint.phase, "advanced": True}


@router.post("/simulation/{team_id}/sprint/reset")
def reset_sprint(team_id: int, db: Session = Depends(get_session)):
    from app.models.sprint import Sprint
    sprint = (
        db.query(Sprint)
        .filter(Sprint.team_id == team_id)
        .order_by(Sprint.id.desc())
        .first()
    )
    if not sprint:
        raise HTTPException(status_code=404, detail="No sprint found")
    sprint.phase = "BACKLOG_PREP"
    sprint.committed_points = 0
    sprint.completed_points = 0
    sprint.goal_at_risk = False
    db.commit()
    return {"id": sprint.id, "phase": "BACKLOG_PREP", "reset": True}


# ── Event config ──


@router.get("/simulation/{team_id}/events")
def get_event_configs(team_id: int, db: Session = Depends(get_session)):
    from app.models.simulation_event_config import SimulationEventConfig
    configs = (
        db.query(SimulationEventConfig)
        .filter(SimulationEventConfig.team_id == team_id)
        .all()
    )
    return [
        {
            "id": c.id,
            "event_type": c.event_type,
            "enabled": c.enabled,
            "probability": c.probability,
            "params": c.params,
        }
        for c in configs
    ]


@router.put("/simulation/{team_id}/events/{event_type}")
def update_event_config(
    team_id: int,
    event_type: str,
    body: EventConfigUpdate,
    db: Session = Depends(get_session),
):
    from app.models.simulation_event_config import SimulationEventConfig
    config = (
        db.query(SimulationEventConfig)
        .filter(
            SimulationEventConfig.team_id == team_id,
            SimulationEventConfig.event_type == event_type,
        )
        .first()
    )
    if not config:
        config = SimulationEventConfig(team_id=team_id, event_type=event_type)
        db.add(config)
    if body.enabled is not None:
        config.enabled = body.enabled
    if body.probability is not None:
        config.probability = body.probability
    if body.params is not None:
        config.params = str(body.params)
    db.commit()
    return {
        "id": config.id,
        "event_type": config.event_type,
        "enabled": config.enabled,
        "probability": config.probability,
    }


# ── Event log ──


@router.get("/simulation/{team_id}/event-log")
def get_event_log(
    team_id: int,
    limit: int = 50,
    db: Session = Depends(get_session),
):
    from app.models.simulation_event_log import SimulationEventLog
    logs = (
        db.query(SimulationEventLog)
        .filter(SimulationEventLog.team_id == team_id)
        .order_by(SimulationEventLog.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": log.id,
            "event_type": log.event_type,
            "sim_day": log.sim_day,
            "payload": log.payload,
            "occurred_at": log.occurred_at.isoformat() if log.occurred_at else None,
        }
        for log in logs
    ]


# ── Backlog ──


@router.get("/simulation/{team_id}/backlog")
def get_backlog(team_id: int, db: Session = Depends(get_session)):
    from app.models.issue import Issue
    issues = (
        db.query(Issue)
        .filter(Issue.team_id == team_id, Issue.status.in_(["BACKLOG", "backlog"]))
        .order_by(Issue.backlog_priority.asc())
        .all()
    )
    return [
        {
            "id": i.id,
            "summary": i.summary,
            "story_points": i.story_points,
            "backlog_priority": i.backlog_priority,
        }
        for i in issues
    ]


@router.post("/simulation/{team_id}/backlog/generate")
async def generate_backlog(
    team_id: int,
    body: BacklogGenerateRequest,
    db: Session = Depends(get_session),
):
    from app.engine.backlog import TemplateContentGenerator, generate_issues
    from app.models.team import Team
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    gen = TemplateContentGenerator()
    issues = await generate_issues(
        count=body.count,
        team_name=team.name,
        content_generator=gen,
    )
    return {"generated": len(issues), "issues": issues}


# ── Capacity ──


@router.get("/simulation/{team_id}/capacity")
def get_capacity(team_id: int, db: Session = Depends(get_session)):
    from app.models.daily_capacity_log import DailyCapacityLog
    from app.models.member import Member
    member_ids = [
        m.id for m in db.query(Member.id).filter(Member.team_id == team_id).all()
    ]
    if not member_ids:
        return []
    logs = (
        db.query(DailyCapacityLog)
        .filter(DailyCapacityLog.member_id.in_(member_ids))
        .order_by(DailyCapacityLog.date.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "member_id": log.member_id,
            "date": log.date.isoformat() if log.date else None,
            "total_hours": log.total_hours,
            "consumed_hours": log.consumed_hours,
            "active_wip_count": log.active_wip_count,
        }
        for log in logs
    ]


# ── Engine health ──


@router.get("/simulation/health", response_model=EngineHealth)
def engine_health(request: Request):
    engine = _get_engine(request)
    return EngineHealth(
        state=engine.state.value.lower(),
        tick_count=engine.tick_count,
        last_successful_tick=(
            engine.last_successful_tick.isoformat()
            if engine.last_successful_tick
            else None
        ),
        paused_teams=sorted(engine.paused_teams),
    )


# ── Legacy inject endpoint ──


@router.post("/simulate/inject", response_model=InjectResponse)
def inject(body: InjectRequest):
    return InjectResponse(injected=True)
