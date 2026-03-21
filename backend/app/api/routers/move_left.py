"""Move-left configuration API — manages regression probability grid."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.models.move_left_config import MoveLeftConfig, MoveLeftTarget
from app.models.team import Team
from app.schemas.move_left import (
    MoveLeftConfigRead,
    MoveLeftReplaceRequest,
)

router = APIRouter(prefix="/teams/{team_id}/move-left", tags=["move-left"])


@router.get("", response_model=list[MoveLeftConfigRead])
def list_move_left_configs(
    team_id: int,
    session: Session = Depends(get_session),
):
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    configs = (
        session.query(MoveLeftConfig)
        .filter_by(team_id=team_id)
        .all()
    )
    return configs


@router.put("", response_model=list[MoveLeftConfigRead])
def replace_move_left_configs(
    team_id: int,
    body: MoveLeftReplaceRequest,
    session: Session = Depends(get_session),
):
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    # Delete existing configs (cascades to targets and same_step_statuses)
    existing = session.query(MoveLeftConfig).filter_by(team_id=team_id).all()
    for cfg in existing:
        session.delete(cfg)
    session.flush()

    # Create new configs
    created = []
    for cfg_input in body.configs:
        config = MoveLeftConfig(
            team_id=team_id,
            from_step_id=cfg_input.from_step_id,
            base_probability=cfg_input.base_probability,
            issue_type=cfg_input.issue_type,
            story_points=cfg_input.story_points,
        )
        session.add(config)
        session.flush()

        for target_input in cfg_input.targets:
            session.add(MoveLeftTarget(
                move_left_config_id=config.id,
                to_step_id=target_input.to_step_id,
                weight=target_input.weight,
            ))

        created.append(config)

    session.commit()
    for cfg in created:
        session.refresh(cfg)
    return created
