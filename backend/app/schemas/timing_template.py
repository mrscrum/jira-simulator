from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TimingTemplateEntryBase(BaseModel):
    issue_type: str
    story_points: int
    ct_min: float
    ct_q1: float
    ct_median: float
    ct_q3: float
    ct_max: float


class TimingTemplateEntryCreate(TimingTemplateEntryBase):
    pass


class TimingTemplateEntryRead(TimingTemplateEntryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    template_id: int
    created_at: datetime
    updated_at: datetime


class TimingTemplateCreate(BaseModel):
    name: str
    description: str | None = None
    spread_factor: float = 0.33
    entries: list[TimingTemplateEntryCreate] = []


class TimingTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    spread_factor: float | None = None
    entries: list[TimingTemplateEntryCreate] | None = None


class TimingTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    spread_factor: float
    entries: list[TimingTemplateEntryRead] = []
    created_at: datetime
    updated_at: datetime


class PreviewConfigItem(BaseModel):
    workflow_step_id: int
    jira_status: str
    status_category: str | None = None
    issue_type: str
    story_points: int
    min_hours: float
    max_hours: float
    full_time_p25: float | None = None
    full_time_p50: float | None = None
    full_time_p99: float | None = None


class TemplatePreviewResponse(BaseModel):
    template_id: int
    team_id: int
    configs: list[PreviewConfigItem]


class TemplateApplyRequest(BaseModel):
    team_ids: list[int]
