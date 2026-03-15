from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CrossTeamDependencyBase(BaseModel):
    source_team_id: int
    target_team_id: int
    dependency_type: str


class CrossTeamDependencyCreate(CrossTeamDependencyBase):
    pass


class CrossTeamDependencyRead(CrossTeamDependencyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
