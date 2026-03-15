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
    created_at: datetime
    updated_at: datetime
