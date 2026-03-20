
from pydantic import BaseModel, ConfigDict


class MoveLeftTargetInput(BaseModel):
    to_step_id: int
    weight: float = 1.0


class MoveLeftConfigInput(BaseModel):
    from_step_id: int
    base_probability: float
    issue_type: str | None = None
    targets: list[MoveLeftTargetInput] = []


class MoveLeftReplaceRequest(BaseModel):
    configs: list[MoveLeftConfigInput]


class MoveLeftTargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    move_left_config_id: int
    to_step_id: int
    weight: float


class MoveLeftConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    from_step_id: int
    base_probability: float
    issue_type: str | None
    targets: list[MoveLeftTargetRead] = []
