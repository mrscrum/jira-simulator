"""E2E setup endpoint — creates 3 demo teams with full data and triggers Jira bootstrap."""

from __future__ import annotations

import logging
import random

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session

from app.engine.backlog import (
    _EPIC_THEMES,
    TemplateContentGenerator,
    generate_issues,
)
from app.engine.issue_state_machine import IssueState
from app.models.dysfunction_config import DysfunctionConfig
from app.models.issue import Issue
from app.models.member import Member
from app.models.organization import Organization
from app.models.team import Team
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/e2e", tags=["e2e"])

# ── Team definitions ──

TEAM_DEFINITIONS = [
    {
        "name": "Platform Engineering",
        "jira_project_key": "PLAT",
        "sprint_length_days": 14,
        "members": [
            ("Alex Chen", "Backend"),
            ("Maria Lopez", "Backend"),
            ("James Park", "Frontend"),
            ("Sophie Turner", "Frontend"),
            ("Raj Patel", "QA"),
            ("Kim Nguyen", "DevOps"),
        ],
        "workflow_steps": [
            ("Backlog", "Backend", 0),
            ("To Do", "Backend", 1),
            ("In Progress", "Backend", 2),
            ("Code Review", "Backend", 3),
            ("QA", "QA", 4),
            ("Done", "Backend", 5),
        ],
        "dysfunctions": {
            "scope_creep_probability": 0.10,
            "blocking_dependency_probability": 0.08,
            "bug_injection_probability": 0.15,
            "low_quality_probability": 0.10,
            "cross_team_block_probability": 0.05,
        },
        "backlog_count": 25,
    },
    {
        "name": "Mobile Squad",
        "jira_project_key": "MOBI",
        "sprint_length_days": 14,
        "members": [
            ("Liam Johnson", "iOS"),
            ("Olivia Davis", "iOS"),
            ("Noah Williams", "Android"),
            ("Emma Brown", "Android"),
            ("Ava Martinez", "QA"),
        ],
        "workflow_steps": [
            ("Backlog", "iOS", 0),
            ("To Do", "iOS", 1),
            ("In Progress", "iOS", 2),
            ("Testing", "QA", 3),
            ("Done", "iOS", 4),
        ],
        "dysfunctions": {
            "scope_creep_probability": 0.25,
            "blocking_dependency_probability": 0.15,
            "bug_injection_probability": 0.20,
            "low_quality_probability": 0.15,
            "cross_team_block_probability": 0.10,
        },
        "backlog_count": 20,
    },
    {
        "name": "Data Analytics",
        "jira_project_key": "DATA",
        "sprint_length_days": 14,
        "members": [
            ("Ethan Miller", "Data Eng"),
            ("Isabella Wilson", "Data Eng"),
            ("Mason Taylor", "ML Eng"),
            ("Charlotte Anderson", "Analyst"),
        ],
        "workflow_steps": [
            ("Backlog", "Data Eng", 0),
            ("To Do", "Data Eng", 1),
            ("In Progress", "Data Eng", 2),
            ("Review", "Data Eng", 3),
            ("Done", "Data Eng", 4),
        ],
        "dysfunctions": {
            "scope_creep_probability": 0.15,
            "blocking_dependency_probability": 0.20,
            "bug_injection_probability": 0.10,
            "low_quality_probability": 0.20,
            "cross_team_block_probability": 0.15,
            "re_estimation_probability": 0.20,
        },
        "backlog_count": 20,
    },
]


def _get_or_create_org(session: Session) -> Organization:
    org = session.query(Organization).first()
    if org:
        return org
    org = Organization(name="Default Organization")
    session.add(org)
    session.flush()
    return org


def _create_team(
    session: Session, org: Organization, defn: dict,
) -> Team:
    """Create a team with members, workflow, dysfunction config, and backlog."""
    # Check if team already exists.
    existing = (
        session.query(Team)
        .filter(Team.jira_project_key == defn["jira_project_key"])
        .first()
    )
    if existing:
        return existing

    team = Team(
        organization_id=org.id,
        name=defn["name"],
        jira_project_key=defn["jira_project_key"],
        sprint_length_days=defn["sprint_length_days"],
        backlog_depth_target=defn["backlog_count"] + 10,
        working_hours_start=0,
        working_hours_end=23,
        timezone="UTC",
    )
    session.add(team)
    session.flush()

    # Members
    for member_name, role in defn["members"]:
        session.add(Member(
            team_id=team.id,
            name=member_name,
            role=role,
            daily_capacity_hours=6.0,
            max_concurrent_wip=3,
        ))

    # Workflow
    workflow = Workflow(team_id=team.id, name=f"{defn['name']} Workflow")
    session.add(workflow)
    session.flush()

    for jira_status, role_required, order in defn["workflow_steps"]:
        session.add(WorkflowStep(
            workflow_id=workflow.id,
            jira_status=jira_status,
            role_required=role_required,
            order=order,
        ))

    # Dysfunction config
    dysf = DysfunctionConfig(team_id=team.id)
    for key, value in defn.get("dysfunctions", {}).items():
        setattr(dysf, key, value)
    session.add(dysf)

    session.flush()
    return team


async def _generate_backlog(
    session: Session, team: Team, count: int,
) -> list[Issue]:
    """Generate backlog issues grouped into epics."""
    rng = random.Random(42 + team.id)
    gen = TemplateContentGenerator(rng=rng)
    generated = await generate_issues(
        count=count,
        team_name=team.name,
        content_generator=gen,
        rng=rng,
    )

    issues: list[Issue] = []
    current_epic = None
    epic_counter = 0

    for idx, g in enumerate(generated):
        # Create a new epic every 5 stories.
        if epic_counter % 5 == 0:
            theme = rng.choice(_EPIC_THEMES)
            current_epic = Issue(
                team_id=team.id,
                issue_type="Epic",
                summary=f"[SIM] Epic: {theme}",
                description=f"Auto-generated epic for {team.name} — {theme}",
                story_points=0,
                status=IssueState.BACKLOG.value,
                backlog_priority=0,
            )
            session.add(current_epic)
            session.flush()
            issues.append(current_epic)

        issue = Issue(
            team_id=team.id,
            issue_type=g["issue_type"],
            summary=g["summary"],
            description=g["description"],
            story_points=g["story_points"],
            status=IssueState.BACKLOG.value,
            backlog_priority=idx + 1,
            epic_id=current_epic.id if current_epic else None,
        )
        session.add(issue)
        issues.append(issue)
        epic_counter += 1

    session.flush()
    return issues


@router.post("/setup")
async def setup_e2e(request: Request):
    """Create 3 demo teams with full data and trigger Jira bootstrap."""
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Session factory not available")

    bootstrapper = getattr(request.app.state, "bootstrapper", None)
    session = session_factory()

    try:
        org = _get_or_create_org(session)
        results = []

        for defn in TEAM_DEFINITIONS:
            team = _create_team(session, org, defn)
            issues = await _generate_backlog(session, team, defn["backlog_count"])
            session.commit()

            # Trigger Jira bootstrap if available.
            bootstrap_status = "skipped"
            if bootstrapper:
                try:
                    await bootstrapper.bootstrap_team(team.id)
                    bootstrap_status = "success"
                except Exception as e:
                    bootstrap_status = f"error: {e}"
                    logger.exception(
                        "Bootstrap failed for team %s: %s", team.name, e,
                    )

            results.append({
                "team_id": team.id,
                "name": team.name,
                "project_key": team.jira_project_key,
                "members": len(defn["members"]),
                "workflow_steps": len(defn["workflow_steps"]),
                "backlog_issues": len(issues),
                "bootstrap": bootstrap_status,
            })

        return {"teams": results}
    except Exception as e:
        session.rollback()
        logger.exception("E2E setup failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
