from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SprintBase(BaseModel):
    name: str
    goal: str | None = None
    start_date: datetime
    end_date: datetime
    status: str = "future"
    planned_velocity: int | None = None
    actual_velocity: int | None = None
    scope_change_points: int = 0
    phase: str = "BACKLOG_PREP"
    sprint_number: int | None = None
    committed_points: int | None = None
    completed_points: int | None = None
    carried_over_points: int = 0
    velocity: float | None = None
    goal_at_risk: bool = False


class SprintCreate(SprintBase):
    team_id: int
    jira_sprint_id: int | None = None


class SprintRead(SprintBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    jira_sprint_id: int | None = None
    created_at: datetime
    updated_at: datetime


class SprintUpdate(BaseModel):
    name: str | None = None
    goal: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str | None = None
    planned_velocity: int | None = None
    actual_velocity: int | None = None
    scope_change_points: int | None = None
    phase: str | None = None
    sprint_number: int | None = None
    committed_points: int | None = None
    completed_points: int | None = None
    carried_over_points: int | None = None
    velocity: float | None = None
    goal_at_risk: bool | None = None
