from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["simulation"])


class SimulationStatus(BaseModel):
    status: str


class TickInterval(BaseModel):
    minutes: int


class InjectRequest(BaseModel):
    team_id: int
    dysfunction_type: str
    target_issue_id: int | None = None
    target_member_id: int | None = None


class InjectResponse(BaseModel):
    injected: bool


@router.get("/simulation/status", response_model=SimulationStatus)
def get_status():
    return SimulationStatus(status="stopped")


@router.post("/simulation/start", response_model=SimulationStatus)
def start():
    return SimulationStatus(status="running")


@router.post("/simulation/pause", response_model=SimulationStatus)
def pause():
    return SimulationStatus(status="paused")


@router.post("/simulation/reset", response_model=SimulationStatus)
def reset():
    return SimulationStatus(status="stopped")


@router.put("/simulation/tick-interval", response_model=TickInterval)
def update_tick_interval(body: TickInterval):
    return body


@router.post("/simulate/inject", response_model=InjectResponse)
def inject(body: InjectRequest):
    return InjectResponse(injected=True)
