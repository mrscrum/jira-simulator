from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.models.team import Team
from app.models.touch_time_config import TouchTimeConfig
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep
from app.schemas.workflow import WorkflowRead
from app.schemas.workflow_step import (
    WorkflowReplaceRequest,
    WorkflowStepCreateRequest,
    WorkflowStepRead,
    WorkflowStepUpdate,
)

router = APIRouter(prefix="/teams/{team_id}/workflow", tags=["workflow"])


def _get_workflow_or_404(team_id: int, session: Session) -> Workflow:
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    workflow = session.query(Workflow).filter_by(team_id=team_id).first()
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.get("", response_model=WorkflowRead)
def get_workflow(team_id: int, session: Session = Depends(get_session)):
    return _get_workflow_or_404(team_id, session)


@router.put("", response_model=WorkflowRead)
def replace_workflow(
    team_id: int,
    body: WorkflowReplaceRequest,
    session: Session = Depends(get_session),
):
    workflow = _get_workflow_or_404(team_id, session)

    # Delete existing steps (cascades to touch_time_configs via relationship)
    for step in workflow.steps:
        for ttc in step.touch_time_configs:
            session.delete(ttc)
        session.delete(step)
    session.flush()

    # Create new steps with touch time configs
    for step_input in body.steps:
        step = WorkflowStep(
            workflow_id=workflow.id,
            jira_status=step_input.jira_status,
            role_required=step_input.role_required,
            order=step_input.order,
            max_wait_hours=step_input.max_wait_hours,
            wip_contribution=step_input.wip_contribution,
        )
        session.add(step)
        session.flush()

        for ttc_input in step_input.touch_time_configs:
            session.add(TouchTimeConfig(
                workflow_step_id=step.id,
                issue_type=ttc_input.issue_type,
                story_points=ttc_input.story_points,
                min_hours=ttc_input.min_hours,
                max_hours=ttc_input.max_hours,
            ))

    session.commit()
    session.refresh(workflow)
    return workflow


@router.post("/steps", response_model=WorkflowStepRead, status_code=201)
def add_step(
    team_id: int,
    body: WorkflowStepCreateRequest,
    session: Session = Depends(get_session),
):
    workflow = _get_workflow_or_404(team_id, session)
    step = WorkflowStep(
        workflow_id=workflow.id,
        jira_status=body.jira_status,
        role_required=body.role_required,
        order=body.order,
        max_wait_hours=body.max_wait_hours,
        wip_contribution=body.wip_contribution,
    )
    session.add(step)
    session.commit()
    session.refresh(step)
    return step


@router.put("/steps/{step_id}", response_model=WorkflowStepRead)
def update_step(
    team_id: int,
    step_id: int,
    body: WorkflowStepUpdate,
    session: Session = Depends(get_session),
):
    workflow = _get_workflow_or_404(team_id, session)
    step = session.query(WorkflowStep).filter_by(
        id=step_id, workflow_id=workflow.id
    ).first()
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(step, field, value)
    session.commit()
    session.refresh(step)
    return step


@router.delete("/steps/{step_id}", response_model=WorkflowStepRead)
def delete_step(
    team_id: int,
    step_id: int,
    session: Session = Depends(get_session),
):
    workflow = _get_workflow_or_404(team_id, session)
    step = session.query(WorkflowStep).filter_by(
        id=step_id, workflow_id=workflow.id
    ).first()
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    session.delete(step)
    session.commit()
    return step
