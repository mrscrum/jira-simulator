from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.models.member import Member
from app.models.team import Team
from app.schemas.member import MemberCreateRequest, MemberRead, MemberUpdate

router = APIRouter(prefix="/teams/{team_id}/members", tags=["members"])


def _get_team_or_404(team_id: int, session: Session) -> Team:
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.get("", response_model=list[MemberRead])
def list_members(team_id: int, session: Session = Depends(get_session)):
    _get_team_or_404(team_id, session)
    return session.query(Member).filter_by(team_id=team_id).all()


@router.post("", response_model=MemberRead, status_code=201)
def create_member(
    team_id: int,
    body: MemberCreateRequest,
    session: Session = Depends(get_session),
):
    _get_team_or_404(team_id, session)
    member = Member(
        team_id=team_id,
        name=body.name,
        role=body.role,
        daily_capacity_hours=body.daily_capacity_hours,
        max_concurrent_wip=body.max_concurrent_wip,
    )
    session.add(member)
    session.commit()
    session.refresh(member)
    return member


@router.put("/{member_id}", response_model=MemberRead)
def update_member(
    team_id: int,
    member_id: int,
    body: MemberUpdate,
    session: Session = Depends(get_session),
):
    member = session.query(Member).filter_by(id=member_id, team_id=team_id).first()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(member, field, value)
    session.commit()
    session.refresh(member)
    return member


@router.delete("/{member_id}", response_model=MemberRead)
def delete_member(
    team_id: int,
    member_id: int,
    session: Session = Depends(get_session),
):
    member = session.query(Member).filter_by(id=member_id, team_id=team_id).first()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    session.delete(member)
    session.commit()
    return member
