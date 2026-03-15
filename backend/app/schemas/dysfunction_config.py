from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DysfunctionConfigBase(BaseModel):
    low_quality_probability: float = 0.15
    scope_creep_probability: float = 0.10
    blocking_dependency_probability: float = 0.12
    dark_teammate_probability: float = 0.05
    re_estimation_probability: float = 0.10
    bug_injection_probability: float = 0.20
    cross_team_block_probability: float = 0.08
    cross_team_handoff_lag_probability: float = 0.10
    cross_team_bug_probability: float = 0.05


class DysfunctionConfigCreate(DysfunctionConfigBase):
    team_id: int


class DysfunctionConfigRead(DysfunctionConfigBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    created_at: datetime
    updated_at: datetime
