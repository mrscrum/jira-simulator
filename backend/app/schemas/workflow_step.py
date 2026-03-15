from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WorkflowStepBase(BaseModel):
    jira_status: str
    role_required: str
    order: int
    max_wait_hours: float = 24.0
    wip_contribution: float = 1.0


class WorkflowStepCreate(WorkflowStepBase):
    workflow_id: int


class WorkflowStepRead(WorkflowStepBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: int
    touch_time_configs: list["TouchTimeConfigRead"] = []
    created_at: datetime
    updated_at: datetime


class WorkflowStepUpdate(BaseModel):
    jira_status: str | None = None
    role_required: str | None = None
    order: int | None = None
    max_wait_hours: float | None = None
    wip_contribution: float | None = None


class WorkflowStepCreateRequest(BaseModel):
    jira_status: str
    role_required: str
    order: int
    max_wait_hours: float = 24.0
    wip_contribution: float = 1.0


class TouchTimeConfigInput(BaseModel):
    issue_type: str
    story_points: int
    min_hours: float
    max_hours: float


class WorkflowStepInput(BaseModel):
    jira_status: str
    role_required: str
    order: int
    max_wait_hours: float = 24.0
    wip_contribution: float = 1.0
    touch_time_configs: list[TouchTimeConfigInput] = []


class WorkflowReplaceRequest(BaseModel):
    steps: list[WorkflowStepInput]


from app.schemas.touch_time_config import TouchTimeConfigRead  # noqa: E402

WorkflowStepRead.model_rebuild()
