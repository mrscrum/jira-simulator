from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.engine.template_engine import apply_template_to_team, generate_preview
from app.models.timing_template import TimingTemplate, TimingTemplateEntry
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep
from app.schemas.timing_template import (
    PreviewConfigItem,
    TemplateApplyRequest,
    TemplatePreviewResponse,
    TimingTemplateCreate,
    TimingTemplateRead,
    TimingTemplateUpdate,
)

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TimingTemplateRead])
def list_templates(session: Session = Depends(get_session)):
    return session.query(TimingTemplate).order_by(TimingTemplate.name).all()


@router.post("", response_model=TimingTemplateRead, status_code=201)
def create_template(body: TimingTemplateCreate, session: Session = Depends(get_session)):
    template = TimingTemplate(
        name=body.name,
        description=body.description,
        spread_factor=body.spread_factor,
    )
    session.add(template)
    session.flush()

    for entry_input in body.entries:
        entry = TimingTemplateEntry(
            template_id=template.id, **entry_input.model_dump()
        )
        session.add(entry)

    session.commit()
    session.refresh(template)
    return template


@router.get("/{template_id}", response_model=TimingTemplateRead)
def get_template(template_id: int, session: Session = Depends(get_session)):
    template = session.get(TimingTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.put("/{template_id}", response_model=TimingTemplateRead)
def update_template(
    template_id: int,
    body: TimingTemplateUpdate,
    session: Session = Depends(get_session),
):
    template = session.get(TimingTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    if body.name is not None:
        template.name = body.name
    if body.description is not None:
        template.description = body.description
    if body.spread_factor is not None:
        template.spread_factor = body.spread_factor

    if body.entries is not None:
        # Delete existing entries and replace
        session.query(TimingTemplateEntry).filter(
            TimingTemplateEntry.template_id == template.id
        ).delete(synchronize_session="fetch")

        for entry_input in body.entries:
            entry = TimingTemplateEntry(
                template_id=template.id, **entry_input.model_dump()
            )
            session.add(entry)

    session.commit()
    session.refresh(template)
    return template


@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: int, session: Session = Depends(get_session)):
    template = session.get(TimingTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    session.delete(template)
    session.commit()


@router.post("/{template_id}/preview", response_model=TemplatePreviewResponse)
def preview_template(
    template_id: int,
    team_id: int,
    session: Session = Depends(get_session),
):
    template = session.get(TimingTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    workflow = (
        session.query(Workflow).filter(Workflow.team_id == team_id).first()
    )
    if workflow is None:
        raise HTTPException(status_code=404, detail="Team workflow not found")

    steps = (
        session.query(WorkflowStep)
        .filter(WorkflowStep.workflow_id == workflow.id)
        .order_by(WorkflowStep.order)
        .all()
    )

    configs = generate_preview(template, steps)
    preview_items = [PreviewConfigItem(**c) for c in configs]

    return TemplatePreviewResponse(
        template_id=template.id,
        team_id=team_id,
        configs=preview_items,
    )


@router.post("/{template_id}/apply")
def apply_template(
    template_id: int,
    body: TemplateApplyRequest,
    session: Session = Depends(get_session),
):
    template = session.get(TimingTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    for team_id in body.team_ids:
        apply_template_to_team(template, team_id, session)

    return {"applied_to": len(body.team_ids)}
