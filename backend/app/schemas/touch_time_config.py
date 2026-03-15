from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TouchTimeConfigBase(BaseModel):
    issue_type: str
    story_points: int
    min_hours: float
    max_hours: float


class TouchTimeConfigCreate(TouchTimeConfigBase):
    workflow_step_id: int


class TouchTimeConfigRead(TouchTimeConfigBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_step_id: int
    created_at: datetime
    updated_at: datetime
