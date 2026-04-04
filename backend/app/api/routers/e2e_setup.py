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
from app.engine.template_engine import apply_template_to_team
from app.models.issue import Issue
from app.models.jira_config import JiraConfig
from app.models.member import Member
from app.models.organization import Organization
from app.models.team import Team
from app.models.timing_template import TimingTemplate, TimingTemplateEntry
from app.models.workflow import Workflow
from app.models.workflow_step import WorkflowStep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/e2e", tags=["e2e"])

# ── Team definitions ──

TEAM_DEFINITIONS = [
    {
        "name": "Platform Engineering",
        "jira_project_key": "PLAT",
        "sprint_length_days": 10,
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
        "sprint_length_days": 10,
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
        "sprint_length_days": 10,
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
        issue_types=["Story", "Bug", "Task"],
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
                status="backlog",
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
            status="backlog",
            backlog_priority=idx + 1,
            epic_id=current_epic.id if current_epic else None,
        )
        session.add(issue)
        issues.append(issue)
        epic_counter += 1

    session.flush()
    return issues


def _get_field_id(session: Session, key: str) -> str | None:
    """Look up a Jira custom field ID from config."""
    row = session.query(JiraConfig).filter(JiraConfig.key == key).first()
    return row.value if row else None


def _build_issue_fields(
    issue: Issue,
    team: Team,
    sp_field: str | None,
    reporter_field: str | None,
    assignee_field: str | None = None,
    epic_jira_key: str | None = None,
) -> dict:
    """Build the Jira fields dict for a CREATE_ISSUE payload."""
    fields: dict = {
        "description": {
            "type": "doc",
            "version": 1,
            "content": [{
                "type": "paragraph",
                "content": [{
                    "type": "text",
                    "text": issue.description or issue.summary,
                }],
            }],
        },
    }
    if sp_field and issue.story_points:
        fields[sp_field] = issue.story_points
    if reporter_field:
        fields[reporter_field] = f"[SIM] {team.name}"
    if assignee_field:
        fields[assignee_field] = "[SIM] Unassigned"
    if epic_jira_key:
        fields["parent"] = {"key": epic_jira_key}
    return fields


async def _sync_issues_to_jira(
    session: Session,
    write_queue,
    team: Team,
    issues: list[Issue],
) -> int:
    """Create all issues in Jira: epics first (processed immediately), then children."""
    # Expire all cached objects so we see field IDs committed by the bootstrapper's
    # separate session.
    session.expire_all()

    sp_field = _get_field_id(session, "field_id_story_points")
    reporter_field = _get_field_id(session, "field_id_sim_reporter")
    assignee_field = _get_field_id(session, "field_id_sim_assignee")

    logger.info(
        "Jira field IDs for %s — sp: %s, reporter: %s, assignee: %s",
        team.name, sp_field, reporter_field, assignee_field,
    )

    epics = [i for i in issues if i.issue_type == "Epic"]
    stories = [i for i in issues if i.issue_type != "Epic"]
    enqueued = 0

    # Metadata for the write queue to route story points via the Agile
    # estimation API (bypasses screen restrictions in simplified projects).
    board_id = team.jira_board_id

    # Phase 1: Enqueue and process epics so they get jira_issue_key.
    for epic in epics:
        fields = _build_issue_fields(
            epic, team, sp_field, reporter_field, assignee_field,
        )
        write_queue.enqueue(
            team_id=team.id,
            operation_type="CREATE_ISSUE",
            payload={
                "project_key": team.jira_project_key,
                "issue_type": "Epic",
                "summary": epic.summary,
                "fields": fields,
                "_board_id": board_id,
                "_sp_field_id": sp_field,
            },
            issue_id=epic.id,
            session=session,
        )
        enqueued += 1
    session.commit()

    # Process epics immediately so jira_issue_key is populated.
    if epics:
        logger.info("Creating %d epics in Jira for %s...", len(epics), team.name)
        await write_queue.process_batch(tick_interval_seconds=60)
        # Refresh epic objects to get the mapped jira_issue_key.
        for epic in epics:
            session.refresh(epic)

    # Phase 2: Enqueue child issues with epic parent links.
    # Build epic_id -> jira_key map for parent linking.
    epic_key_map: dict[int, str | None] = {
        e.id: e.jira_issue_key for e in epics
    }

    for story in stories:
        epic_key = epic_key_map.get(story.epic_id) if story.epic_id else None
        fields = _build_issue_fields(
            story, team, sp_field, reporter_field, assignee_field,
            epic_jira_key=epic_key,
        )
        write_queue.enqueue(
            team_id=team.id,
            operation_type="CREATE_ISSUE",
            payload={
                "project_key": team.jira_project_key,
                "issue_type": story.issue_type,
                "summary": f"[SIM] {story.summary}",
                "fields": fields,
                "_board_id": board_id,
                "_sp_field_id": sp_field,
            },
            issue_id=story.id,
            session=session,
        )
        enqueued += 1
    session.commit()

    return enqueued


# ── Default timing template ──
# Realistic cycle-time distributions (in hours) for Story issues by SP.
# Based on typical Scrum team data: ct_min, ct_q1, ct_median, ct_q3, ct_max.
_CYCLE_TIME_BY_SP = {
    1:  (1.0,  2.0,  4.0,  6.0,  12.0),
    2:  (2.0,  4.0,  8.0,  12.0, 24.0),
    3:  (3.0,  6.0,  12.0, 18.0, 36.0),
    5:  (5.0,  10.0, 20.0, 30.0, 60.0),
    8:  (8.0,  16.0, 32.0, 48.0, 96.0),
    13: (12.0, 24.0, 48.0, 72.0, 144.0),
}

DEFAULT_TEMPLATE_ENTRIES = [
    {
        "issue_type": issue_type,
        "story_points": sp,
        "ct_min": vals[0] * scale,
        "ct_q1": vals[1] * scale,
        "ct_median": vals[2] * scale,
        "ct_q3": vals[3] * scale,
        "ct_max": vals[4] * scale,
    }
    for issue_type, scale in [
        ("Story", 1.0),
        ("Bug", 0.7),    # bugs are typically faster to fix
        ("Task", 0.8),   # tasks are slightly faster than stories
    ]
    for sp, vals in _CYCLE_TIME_BY_SP.items()
]


def _create_default_template(session: Session) -> TimingTemplate:
    """Create or return the default timing template."""
    existing = (
        session.query(TimingTemplate)
        .filter(TimingTemplate.name == "Default Scrum Template")
        .first()
    )
    if existing:
        return existing

    template = TimingTemplate(
        name="Default Scrum Template",
        description=(
            "Realistic cycle-time distributions for Scrum teams. "
            "Auto-created by E2E setup."
        ),
        spread_factor=0.33,
    )
    session.add(template)
    session.flush()

    for entry_data in DEFAULT_TEMPLATE_ENTRIES:
        session.add(TimingTemplateEntry(
            template_id=template.id, **entry_data,
        ))

    session.flush()
    logger.info("Created default timing template with %d entries",
                len(DEFAULT_TEMPLATE_ENTRIES))
    return template


@router.post("/setup")
async def setup_e2e(request: Request):
    """Create 3 demo teams with full data and trigger Jira bootstrap."""
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Session factory not available")

    bootstrapper = getattr(request.app.state, "bootstrapper", None)
    write_queue = getattr(request.app.state, "write_queue", None)
    session = session_factory()

    try:
        org = _get_or_create_org(session)
        results = []

        # Create default timing template (idempotent).
        template = _create_default_template(session)
        session.commit()

        for defn in TEAM_DEFINITIONS:
            team = _create_team(session, org, defn)
            issues = await _generate_backlog(session, team, defn["backlog_count"])
            session.commit()

            # Apply timing template to team (creates TouchTimeConfigs).
            try:
                apply_template_to_team(template, team.id, session)
                logger.info("Applied timing template to team %s", team.name)
            except Exception as e:
                logger.warning(
                    "Failed to apply template to team %s: %s",
                    team.name, e,
                )

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

            # Create all issues in Jira (epics first, then stories).
            jira_issues_enqueued = 0
            if write_queue and bootstrap_status == "success":
                # Re-read team to get fresh bootstrap data.
                session.expire(team)
                jira_issues_enqueued = await _sync_issues_to_jira(
                    session, write_queue, team, issues,
                )
                logger.info(
                    "Enqueued %d issues for Jira creation (team %s)",
                    jira_issues_enqueued, team.name,
                )

            results.append({
                "team_id": team.id,
                "name": team.name,
                "project_key": team.jira_project_key,
                "members": len(defn["members"]),
                "workflow_steps": len(defn["workflow_steps"]),
                "backlog_issues": len(issues),
                "bootstrap": bootstrap_status,
                "jira_issues_enqueued": jira_issues_enqueued,
            })

        # Process the Jira write queue to create issues in Jira.
        # We run multiple batches to handle all queued items (78+ issues).
        if write_queue:
            try:
                logger.info("Processing Jira write queue after E2E setup...")
                for batch_num in range(20):  # Up to 20 batches
                    pending = write_queue.get_pending_batch()
                    if not pending:
                        logger.info(
                            "Queue empty after %d batches", batch_num,
                        )
                        break
                    logger.info(
                        "Processing batch %d (%d entries)...",
                        batch_num + 1, len(pending),
                    )
                    await write_queue.process_batch(
                        tick_interval_seconds=120,
                    )
            except Exception as e:
                logger.exception("Queue processing error: %s", e)

        return {"teams": results}
    except Exception as e:
        session.rollback()
        logger.exception("E2E setup failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/prepare-simulation")
async def prepare_simulation(request: Request):
    """Configure teams for sprint simulation testing.

    Sets shorter sprint lengths and returns readiness info.
    Call this before POST /simulation/start.
    """
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Session factory not available")

    session = session_factory()
    try:
        teams = session.query(Team).filter(Team.is_active.is_(True)).all()
        if not teams:
            raise HTTPException(
                status_code=404,
                detail="No teams found. Run POST /e2e/setup first.",
            )

        team_info = []
        for team in teams:
            # Ensure no pause before planning.
            team.pause_before_planning = False

            # Count backlog issues.
            backlog_count = (
                session.query(Issue)
                .filter(
                    Issue.team_id == team.id,
                    Issue.status.in_(["BACKLOG", "backlog"]),
                )
                .count()
            )
            members_count = (
                session.query(Member)
                .filter(Member.team_id == team.id, Member.is_active.is_(True))
                .count()
            )
            sprint_capacity = members_count * team.sprint_length_days
            backlog_threshold = int(sprint_capacity * 1.5)

            team_info.append({
                "team_id": team.id,
                "name": team.name,
                "sprint_length_days": team.sprint_length_days,
                "backlog_issues": backlog_count,
                "members": members_count,
                "sprint_capacity": sprint_capacity,
                "backlog_threshold_for_planning": backlog_threshold,
                "ready_for_planning": backlog_count >= backlog_threshold,
                "jira_board_id": team.jira_board_id,
                "jira_project_key": team.jira_project_key,
            })

        session.commit()

        return {
            "message": "Simulation prepared. Teams ready for sprint precompute.",
            "instructions": [
                "1. Pre-compute sprint: POST /teams/{id}/sprints/precompute",
                "2. Start simulation: POST /simulation/start",
                "3. Monitor: GET /simulation/status",
            ],
            "teams": team_info,
        }
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.exception("Prepare simulation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/diagnostics")
async def diagnostics(request: Request):
    """Return diagnostic info about JiraConfig field IDs and sample issue data."""
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Session factory not available")

    jira_client = getattr(request.app.state, "jira_client", None)
    session = session_factory()

    try:
        # All JiraConfig entries.
        configs = session.query(JiraConfig).all()
        config_data = {c.key: c.value for c in configs}

        # Sample issues with story points.
        sample_issues = (
            session.query(Issue)
            .filter(Issue.story_points > 0, Issue.jira_issue_key.isnot(None))
            .limit(3)
            .all()
        )
        issue_data = [
            {
                "id": i.id,
                "jira_key": i.jira_issue_key,
                "type": i.issue_type,
                "story_points": i.story_points,
                "summary": i.summary[:60],
            }
            for i in sample_issues
        ]

        # Check a sample issue in Jira to see actual field values.
        jira_issue_detail = None
        if jira_client and sample_issues:
            try:
                jira_data = await jira_client.get_issue(
                    sample_issues[0].jira_issue_key,
                )
                jira_fields = jira_data.get("fields", {})
                # Extract only our custom fields.
                sp_fid = config_data.get("field_id_story_points")
                rep_fid = config_data.get("field_id_sim_reporter")
                asg_fid = config_data.get("field_id_sim_assignee")
                # Dump ALL customfield_* values to see what Jira has.
                all_custom = {
                    k: v for k, v in jira_fields.items()
                    if k.startswith("customfield_") and v is not None
                }
                jira_issue_detail = {
                    "key": jira_data.get("key"),
                    "story_points_field": sp_fid,
                    "story_points_value": (
                        jira_fields.get(sp_fid) if sp_fid else None
                    ),
                    "reporter_field": rep_fid,
                    "reporter_value": (
                        jira_fields.get(rep_fid) if rep_fid else None
                    ),
                    "assignee_field": asg_fid,
                    "assignee_value": (
                        jira_fields.get(asg_fid) if asg_fid else None
                    ),
                    "summary": jira_fields.get("summary"),
                    "issue_type": jira_fields.get(
                        "issuetype", {},
                    ).get("name"),
                    "status": jira_fields.get(
                        "status", {},
                    ).get("name"),
                    "all_custom_fields_with_values": all_custom,
                }
            except Exception as e:
                jira_issue_detail = {"error": str(e)}

        # Check board configuration for estimation field.
        board_config = None
        if jira_client:
            try:
                teams = session.query(Team).limit(1).all()
                if teams and teams[0].jira_board_id:
                    bid = teams[0].jira_board_id
                    resp = await jira_client._request(
                        "GET",
                        f"/rest/agile/1.0/board/{bid}/configuration",
                    )
                    cfg = resp.json()
                    board_config = {
                        "board_id": bid,
                        "estimation_field": cfg.get(
                            "estimation", {},
                        ).get("field", {}),
                        "board_name": cfg.get("name"),
                    }
            except Exception as e:
                board_config = {"error": str(e)}

        # Queue stats.
        from app.models.jira_write_queue_entry import JiraWriteQueueEntry

        queue_stats = {}
        for status in ("PENDING", "DONE", "FAILED", "IN_FLIGHT"):
            count = (
                session.query(JiraWriteQueueEntry)
                .filter(JiraWriteQueueEntry.status == status)
                .count()
            )
            queue_stats[status] = count

        return {
            "jira_config": config_data,
            "sample_local_issues": issue_data,
            "jira_issue_detail": jira_issue_detail,
            "board_config": board_config,
            "queue_stats": queue_stats,
        }
    finally:
        session.close()
