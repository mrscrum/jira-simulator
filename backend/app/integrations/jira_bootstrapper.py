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

# Preferred story-points field ID (Jira native "Story Points" field).
# Detected from the live instance via /rest/api/3/field.
PREFERRED_SP_FIELD_ID = "customfield_10034"

# Fallback names if the preferred field doesn't exist.
BUILTIN_SP_NAMES = ("Story Points", "Story point estimate", "story_points")

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
        await self._ensure_custom_fields(session, team)
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

    async def _ensure_custom_fields(
        self, session: Session, team: Team,
    ) -> None:
        existing_fields = await self._jira.get_custom_fields()
        existing_by_id = {f["id"]: f for f in existing_fields}
        existing_names = {f["name"]: f["id"] for f in existing_fields}

        # --- Detect story points field ---
        # 1. Preferred: use the known native field ID directly.
        # 2. Fallback: read the board's estimation configuration.
        # 3. Last resort: scan field names for common SP names.
        sp_field_id = None

        if PREFERRED_SP_FIELD_ID in existing_by_id:
            sp_field_id = PREFERRED_SP_FIELD_ID
            logger.info(
                "Using preferred story points field: %s (%s)",
                existing_by_id[sp_field_id]["name"], sp_field_id,
            )

        if sp_field_id is None and team.jira_board_id:
            try:
                resp = await self._jira._request(
                    "GET",
                    f"/rest/agile/1.0/board/{team.jira_board_id}/configuration",
                )
                board_cfg = resp.json()
                est = board_cfg.get("estimation", {}).get("field", {})
                board_sp_id = est.get("fieldId")
                if board_sp_id:
                    sp_field_id = board_sp_id
                    logger.info(
                        "Using board estimation field: %s (%s)",
                        est.get("displayName", ""), sp_field_id,
                    )
            except Exception as exc:
                logger.warning("Could not read board config: %s", exc)

        if sp_field_id is None:
            for sp_name in BUILTIN_SP_NAMES:
                if sp_name in existing_names:
                    sp_field_id = existing_names[sp_name]
                    logger.info(
                        "Using built-in story points field: %s (%s)",
                        sp_name, sp_field_id,
                    )
                    break

        if sp_field_id:
            self._upsert_config(session, "field_id_story_points", sp_field_id)
        else:
            logger.warning("No story points field found in Jira")

        # --- Custom fields (sim_assignee, sim_reporter) ---
        all_field_ids: list[str] = []
        if sp_field_id:
            all_field_ids.append(sp_field_id)

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
            all_field_ids.append(field_id)

        # --- Add all fields to Jira screens so they are settable ---
        for fid in all_field_ids:
            try:
                count = await self._jira.add_field_to_all_screens(fid)
                logger.info("Added field %s to %d screen(s)", fid, count)
            except Exception as exc:
                logger.warning("Could not add field %s to screens: %s", fid, exc)

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
