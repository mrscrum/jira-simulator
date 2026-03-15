from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.models.dysfunction_config import DysfunctionConfig
from app.models.team import Team
from app.schemas.dysfunction_config import DysfunctionConfigRead, DysfunctionConfigUpdate

router = APIRouter(prefix="/teams/{team_id}/dysfunctions", tags=["dysfunctions"])

VALID_DYSFUNCTION_TYPES = {
    "low_quality",
    "scope_creep",
    "blocking_dependency",
    "dark_teammate",
    "re_estimation",
    "bug_injection",
    "cross_team_block",
    "cross_team_handoff_lag",
    "cross_team_bug",
}


@router.get("", response_model=DysfunctionConfigRead)
def get_dysfunctions(team_id: int, session: Session = Depends(get_session)):
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    config = session.query(DysfunctionConfig).filter_by(team_id=team_id).first()
    if config is None:
        raise HTTPException(status_code=404, detail="Dysfunction config not found")
    return config


@router.put("/{dysfunction_type}", response_model=DysfunctionConfigRead)
def update_dysfunction(
    team_id: int,
    dysfunction_type: str,
    body: DysfunctionConfigUpdate,
    session: Session = Depends(get_session),
):
    if dysfunction_type not in VALID_DYSFUNCTION_TYPES:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown dysfunction type: {dysfunction_type}",
        )
    config = session.query(DysfunctionConfig).filter_by(team_id=team_id).first()
    if config is None:
        raise HTTPException(status_code=404, detail="Dysfunction config not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(config, field, value)
    session.commit()
    session.refresh(config)
    return config
