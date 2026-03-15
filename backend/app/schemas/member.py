from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MemberBase(BaseModel):
    name: str
    role: str
    daily_capacity_hours: float = 6.0
    max_concurrent_wip: int = 3
    is_active: bool = True


class MemberCreate(MemberBase):
    team_id: int


class MemberCreateRequest(BaseModel):
    name: str
    role: str
    daily_capacity_hours: float = 6.0
    max_concurrent_wip: int = 3


class MemberRead(MemberBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    created_at: datetime
    updated_at: datetime


class MemberUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    daily_capacity_hours: float | None = None
    max_concurrent_wip: int | None = None
    is_active: bool | None = None
