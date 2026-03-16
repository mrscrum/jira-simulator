from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.models.dysfunction_config import DysfunctionConfig
from app.models.organization import Organization
from app.models.team import Team
from app.models.workflow import Workflow
from app.schemas.team import TeamCreateRequest, TeamRead, TeamUpdate

router = APIRouter(prefix="/teams", tags=["teams"])

DEFAULT_ORGANIZATION_NAME = "Default Organization"


def _get_or_create_organization(session: Session) -> Organization:
    org = session.query(Organization).first()
    if org is not None:
        return org
    org = Organization(name=DEFAULT_ORGANIZATION_NAME)
    session.add(org)
    session.flush()
    return org


@router.get("", response_model=list[TeamRead])
def list_teams(session: Session = Depends(get_session)):
    return session.query(Team).all()


@router.post("", response_model=TeamRead, status_code=201)
def create_team(
    body: TeamCreateRequest,
    session: Session = Depends(get_session),
):
    org = _get_or_create_organization(session)
    team = Team(
        organization_id=org.id,
        name=body.name,
        jira_project_key=body.jira_project_key,
        jira_board_id=body.jira_board_id,
        sprint_length_days=body.sprint_length_days,
        sprint_planning_strategy=body.sprint_planning_strategy,
        backlog_depth_target=body.backlog_depth_target,
        pause_before_planning=body.pause_before_planning,
        working_hours_start=body.working_hours_start,
        working_hours_end=body.working_hours_end,
        timezone=body.timezone,
        holidays=body.holidays,
    )
    session.add(team)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Project key '{body.jira_project_key}' already exists",
        )

    session.add(DysfunctionConfig(team_id=team.id))
    session.add(Workflow(team_id=team.id, name=f"{body.name} Workflow"))
    session.commit()
    session.refresh(team)
    return team


@router.get("/{team_id}", response_model=TeamRead)
def get_team(team_id: int, session: Session = Depends(get_session)):
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.put("/{team_id}", response_model=TeamRead)
def update_team(
    team_id: int,
    body: TeamUpdate,
    session: Session = Depends(get_session),
):
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(team, field, value)
    session.commit()
    session.refresh(team)
    return team


@router.delete("/{team_id}", response_model=TeamRead)
def delete_team(team_id: int, session: Session = Depends(get_session)):
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    team.is_active = False
    session.commit()
    session.refresh(team)
    return team
