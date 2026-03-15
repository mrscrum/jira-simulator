from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.models.cross_team_dependency import CrossTeamDependency
from app.schemas.cross_team_dependency import (
    CrossTeamDependencyCreate,
    CrossTeamDependencyRead,
)

router = APIRouter(prefix="/dependencies", tags=["dependencies"])


@router.get("", response_model=list[CrossTeamDependencyRead])
def list_dependencies(session: Session = Depends(get_session)):
    return session.query(CrossTeamDependency).all()


@router.post("", response_model=CrossTeamDependencyRead, status_code=201)
def create_dependency(
    body: CrossTeamDependencyCreate,
    session: Session = Depends(get_session),
):
    if body.source_team_id == body.target_team_id:
        raise HTTPException(
            status_code=400,
            detail="Source and target team must differ",
        )
    dep = CrossTeamDependency(
        source_team_id=body.source_team_id,
        target_team_id=body.target_team_id,
        dependency_type=body.dependency_type,
    )
    session.add(dep)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Dependency already exists")
    session.refresh(dep)
    return dep


@router.delete("/{dependency_id}", response_model=CrossTeamDependencyRead)
def delete_dependency(
    dependency_id: int,
    session: Session = Depends(get_session),
):
    dep = session.get(CrossTeamDependency, dependency_id)
    if dep is None:
        raise HTTPException(status_code=404, detail="Dependency not found")
    session.delete(dep)
    session.commit()
    return dep
