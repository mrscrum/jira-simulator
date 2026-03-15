from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WorkflowBase(BaseModel):
    name: str
    description: str | None = None


class WorkflowCreate(WorkflowBase):
    team_id: int


class WorkflowRead(WorkflowBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    steps: list["WorkflowStepRead"] = []
    created_at: datetime
    updated_at: datetime


from app.schemas.workflow_step import WorkflowStepRead  # noqa: E402

WorkflowRead.model_rebuild()
