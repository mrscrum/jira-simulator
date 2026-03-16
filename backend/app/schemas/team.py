from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TeamBase(BaseModel):
    name: str
    jira_project_key: str
    jira_board_id: int | None = None
    is_active: bool = True
    sprint_length_days: int = 10
    sprint_planning_strategy: str = "capacity_fitted"
    backlog_depth_target: int = 40
    pause_before_planning: bool = False
    working_hours_start: int = 9
    working_hours_end: int = 17
    timezone: str = "UTC"
    holidays: str = "[]"


class TeamCreate(TeamBase):
    organization_id: int


class TeamCreateRequest(BaseModel):
    name: str
    jira_project_key: str
    jira_board_id: int | None = None


class TeamRead(TeamBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    created_at: datetime
    updated_at: datetime


class TeamUpdate(BaseModel):
    name: str | None = None
    jira_project_key: str | None = None
    jira_board_id: int | None = None
    is_active: bool | None = None
    sprint_length_days: int | None = None
    sprint_planning_strategy: str | None = None
    backlog_depth_target: int | None = None
    pause_before_planning: bool | None = None
    working_hours_start: int | None = None
    working_hours_end: int | None = None
    timezone: str | None = None
    holidays: str | None = None
