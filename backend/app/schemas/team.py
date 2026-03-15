from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TeamBase(BaseModel):
    name: str
    jira_project_key: str
    jira_board_id: int | None = None
    is_active: bool = True


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
