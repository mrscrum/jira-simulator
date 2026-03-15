import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.models.jira_write_queue_entry import JiraWriteQueueEntry
from app.models.team import Team
from app.schemas.jira import (
    BootstrapStatusResponse,
    JiraHealthResponse,
    JiraStatus,
    QueueStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jira", tags=["jira"])

FALLBACK_STATUSES = [
    {"name": "To Do", "category": "new"},
    {"name": "In Progress", "category": "indeterminate"},
    {"name": "In Review", "category": "indeterminate"},
    {"name": "QA", "category": "indeterminate"},
    {"name": "Done", "category": "done"},
]


def get_jira_client(request: Request):
    return getattr(request.app.state, "jira_client", None)


def get_health_monitor(request: Request):
    return getattr(request.app.state, "health_monitor", None)


def get_bootstrapper(request: Request):
    return getattr(request.app.state, "bootstrapper", None)


def get_write_queue(request: Request):
    return getattr(request.app.state, "write_queue", None)


def _get_team_or_404(team_id: int, session: Session) -> Team:
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.post("/bootstrap/{team_id}")
async def bootstrap_team(
    team_id: int,
    session: Session = Depends(get_session),
    bootstrapper=Depends(get_bootstrapper),
):
    _get_team_or_404(team_id, session)
    await bootstrapper.bootstrap_team(team_id)
    return {"status": "ok", "team_id": team_id}


@router.get(
    "/bootstrap/{team_id}/status",
    response_model=BootstrapStatusResponse,
)
def bootstrap_status(
    team_id: int,
    session: Session = Depends(get_session),
):
    team = _get_team_or_404(team_id, session)
    warnings = []
    if team.jira_bootstrap_warnings:
        warnings = json.loads(team.jira_bootstrap_warnings)

    custom_fields = _get_custom_field_ids(session)

    return BootstrapStatusResponse(
        bootstrapped=team.jira_bootstrapped,
        warnings=warnings,
        board_id=team.jira_board_id,
        custom_field_ids=custom_fields,
        last_run=team.jira_bootstrapped_at,
    )


def _get_custom_field_ids(session: Session) -> dict[str, str]:
    from app.models.jira_config import JiraConfig

    configs = (
        session.query(JiraConfig)
        .filter(JiraConfig.key.like("field_id_%"))
        .all()
    )
    return {c.key.replace("field_id_", ""): c.value for c in configs}


@router.get("/health", response_model=JiraHealthResponse)
def jira_health(health_monitor=Depends(get_health_monitor)):
    return JiraHealthResponse(
        status=health_monitor.status,
        last_checked=health_monitor.last_checked,
        last_online=health_monitor.last_online,
        consecutive_failures=health_monitor.consecutive_failures,
        outage_start=health_monitor.outage_start,
    )


@router.get("/queue/status", response_model=QueueStatusResponse)
def queue_status(session: Session = Depends(get_session)):
    counts = _count_queue_entries(session)
    return QueueStatusResponse(**counts)


def _count_queue_entries(session: Session) -> dict[str, int]:
    all_entries = session.query(JiraWriteQueueEntry).all()
    status_counts = {
        "pending": 0,
        "in_flight": 0,
        "done": 0,
        "failed": 0,
        "skipped": 0,
    }
    for entry in all_entries:
        key = entry.status.lower()
        if key in status_counts:
            status_counts[key] += 1
    status_counts["total"] = len(all_entries)
    return status_counts


@router.post("/queue/retry-failed")
def retry_failed(write_queue=Depends(get_write_queue)):
    count = write_queue.retry_failed()
    return {"retried": count}


@router.get(
    "/projects/{project_key}/statuses",
    response_model=list[JiraStatus],
)
async def project_statuses(
    project_key: str,
    jira_client=Depends(get_jira_client),
):
    try:
        raw_statuses = await jira_client.get_project_statuses(project_key)
        return [
            JiraStatus(
                name=s["name"],
                category=s.get("statusCategory", {}).get("key", "unknown"),
            )
            for s in raw_statuses
        ]
    except Exception:
        logger.warning(
            "Failed to fetch statuses from Jira, using fallback"
        )
        return [JiraStatus(**s) for s in FALLBACK_STATUSES]
