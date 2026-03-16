import json
import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.integrations.alerting import AlertEvent
from app.models.jira_config import JiraConfig
from app.models.team import Team
from app.models.workflow import Workflow

logger = logging.getLogger(__name__)

# Only sim_assignee and sim_reporter are custom-created.
# Story points uses Jira's built-in "Story point estimate" field.
REQUIRED_CUSTOM_FIELDS = [
    ("sim_assignee", "com.atlassian.jira.plugin.system.customfieldtypes:textfield"),
    ("sim_reporter", "com.atlassian.jira.plugin.system.customfieldtypes:textfield"),
]

# Known names for Jira's built-in story points field.
BUILTIN_SP_NAMES = ("Story point estimate", "Story Points", "story_points")

AlertFn = Callable[[AlertEvent, dict], Coroutine[Any, Any, None]]


class JiraBootstrapper:
    def __init__(
        self,
        jira_client: Any,
        session_factory: Any,
        send_alert: AlertFn,
    ):
        self._jira = jira_client
        self._session_factory = session_factory
        self._send_alert = send_alert

    def _get_session(self) -> Session:
        return self._session_factory()

    async def bootstrap_team(self, team_id: int) -> None:
        session = self._get_session()
        team = session.get(Team, team_id)
        if team is None:
            raise ValueError(f"Team {team_id} not found")

        warnings: list[str] = []

        await self._ensure_project(team)
        await self._ensure_board(team)
        await self._ensure_custom_fields(session)
        status_warnings = await self._match_statuses(team, session)
        warnings.extend(status_warnings)

        self._finalize(team, warnings, session)

        if warnings:
            await self._send_alert(
                AlertEvent.BOOTSTRAP_INCOMPLETE,
                {"team": team.name},
            )

    async def _ensure_project(self, team: Team) -> None:
        existing = await self._jira.get_project(team.jira_project_key)
        if existing:
            logger.info("Project %s found, skipping", team.jira_project_key)
            return
        await self._jira.create_project(
            team.jira_project_key, team.name, "scrum"
        )
        logger.info("Created project %s", team.jira_project_key)

    async def _ensure_board(self, team: Team) -> None:
        board = await self._jira.get_board(team.jira_project_key)
        if board:
            team.jira_board_id = board["id"]
            return
        # Jira Cloud auto-creates a board when a simplified project is created.
        # Retry once; if still missing, log warning but continue.
        import asyncio
        await asyncio.sleep(2)
        board = await self._jira.get_board(team.jira_project_key)
        if board:
            team.jira_board_id = board["id"]
        else:
            logger.warning(
                "Board not found for project %s after creation",
                team.jira_project_key,
            )

    async def _ensure_custom_fields(self, session: Session) -> None:
        existing_fields = await self._jira.get_custom_fields()
        existing_names = {f["name"]: f["id"] for f in existing_fields}

        # --- Detect Jira's built-in story points field ---
        sp_field_id = None
        for sp_name in BUILTIN_SP_NAMES:
            if sp_name in existing_names:
                sp_field_id = existing_names[sp_name]
                logger.info("Using built-in story points field: %s (%s)", sp_name, sp_field_id)
                break
        if sp_field_id is None:
            # Fallback: look for any field whose name contains "story point"
            for name, fid in existing_names.items():
                if "story point" in name.lower():
                    sp_field_id = fid
                    logger.info("Using story points field: %s (%s)", name, sp_field_id)
                    break
        if sp_field_id:
            self._upsert_config(session, "field_id_story_points", sp_field_id)
        else:
            logger.warning("No built-in story points field found in Jira")

        # --- Custom fields (sim_assignee, sim_reporter) ---
        for field_name, field_type in REQUIRED_CUSTOM_FIELDS:
            config_key = f"field_id_{field_name}"
            if field_name in existing_names:
                field_id = existing_names[field_name]
            else:
                result = await self._jira.create_custom_field(
                    field_name, field_type
                )
                field_id = result["id"]
                logger.info("Created custom field: %s", field_name)

            self._upsert_config(session, config_key, field_id)
        session.flush()

    @staticmethod
    def _upsert_config(session: Session, key: str, value: str) -> None:
        existing = (
            session.query(JiraConfig)
            .filter(JiraConfig.key == key)
            .first()
        )
        if existing:
            existing.value = value
        else:
            session.add(JiraConfig(key=key, value=value))

    async def _match_statuses(
        self, team: Team, session: Session
    ) -> list[str]:
        warnings: list[str] = []
        workflow = (
            session.query(Workflow)
            .filter(Workflow.team_id == team.id)
            .first()
        )
        if not workflow or not workflow.steps:
            return warnings

        jira_statuses = await self._jira.get_project_statuses(
            team.jira_project_key
        )
        jira_status_names = {s["name"] for s in jira_statuses}

        for step in workflow.steps:
            if step.jira_status not in jira_status_names:
                msg = (
                    f"Status '{step.jira_status}' not found in "
                    f"Jira project {team.jira_project_key}. "
                    f"Please create it manually, then re-run bootstrap."
                )
                warnings.append(msg)
                logger.warning(msg)

        return warnings

    def _finalize(
        self, team: Team, warnings: list[str], session: Session
    ) -> None:
        team.jira_bootstrapped = True
        team.jira_bootstrapped_at = datetime.now(UTC)
        team.jira_bootstrap_warnings = json.dumps(warnings) if warnings else None
        session.commit()
        logger.info("Bootstrap complete for team %s", team.name)
