import base64
import logging
from datetime import datetime

import httpx

from app.integrations.exceptions import (
    JiraAuthError,
    JiraConnectionError,
    JiraNotFoundError,
    JiraRateLimitError,
)

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 30


class JiraClient:
    def __init__(self, base_url: str, email: str, api_token: str):
        self._base_url = base_url.rstrip("/")
        credentials = base64.b64encode(
            f"{email}:{api_token}".encode()
        ).decode()
        self._auth_header = f"Basic {credentials}"
        self._http = httpx.AsyncClient(timeout=TIMEOUT_SECONDS)

    async def close(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self._base_url}{path}"
        headers = {
            "Authorization": self._auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            response = await self._http.request(
                method, url, headers=headers, **kwargs
            )
        except httpx.ConnectError as exc:
            raise JiraConnectionError(str(exc)) from exc

        self._check_status(response)
        return response

    def _check_status(self, response: httpx.Response) -> None:
        code = response.status_code
        if code in (401, 403):
            raise JiraAuthError(f"Auth failed: {code}")
        if code == 404:
            raise JiraNotFoundError(f"Not found: {response.url}")
        if code == 429:
            retry_after = float(response.headers.get("Retry-After", "60"))
            raise JiraRateLimitError(retry_after)
        if code >= 400:
            raise JiraConnectionError(f"HTTP {code}: {response.text[:200]}")

    # --- Health ---

    async def ping(self) -> bool:
        try:
            await self._request("GET", "/rest/api/3/myself")
            return True
        except (JiraConnectionError, JiraAuthError):
            return False

    # --- Projects ---

    async def get_project(self, project_key: str) -> dict | None:
        try:
            response = await self._request(
                "GET", f"/rest/api/3/project/{project_key}"
            )
            return response.json()
        except JiraNotFoundError:
            return None

    async def get_myself(self) -> dict:
        response = await self._request("GET", "/rest/api/3/myself")
        return response.json()

    async def create_project(
        self, key: str, name: str, board_type: str
    ) -> dict:
        myself = await self.get_myself()
        payload = {
            "key": key,
            "name": name,
            "projectTypeKey": "software",
            "projectTemplateKey": self._template_key(board_type),
            "leadAccountId": myself["accountId"],
        }
        response = await self._request(
            "POST", "/rest/api/3/project", json=payload
        )
        return response.json()

    def _template_key(self, board_type: str) -> str:
        if board_type == "scrum":
            return "com.pyxis.greenhopper.jira:gh-simplified-scrum-classic"
        return "com.pyxis.greenhopper.jira:gh-simplified-kanban-classic"

    # --- Boards & Sprints ---

    async def get_board(self, project_key: str) -> dict | None:
        response = await self._request(
            "GET",
            "/rest/agile/1.0/board",
            params={"projectKeyOrId": project_key},
        )
        boards = response.json().get("values", [])
        return boards[0] if boards else None

    async def get_active_sprint(self, board_id: int) -> dict | None:
        response = await self._request(
            "GET",
            f"/rest/agile/1.0/board/{board_id}/sprint",
            params={"state": "active"},
        )
        sprints = response.json().get("values", [])
        return sprints[0] if sprints else None

    async def create_sprint(
        self,
        board_id: int,
        name: str,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        payload = {
            "name": name,
            "originBoardId": board_id,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
        }
        response = await self._request(
            "POST", "/rest/agile/1.0/sprint", json=payload
        )
        return response.json()

    async def start_sprint(self, sprint_id: int) -> dict:
        response = await self._request(
            "POST",
            f"/rest/agile/1.0/sprint/{sprint_id}",
            json={"state": "active"},
        )
        return response.json()

    async def complete_sprint(self, sprint_id: int) -> dict:
        response = await self._request(
            "POST",
            f"/rest/agile/1.0/sprint/{sprint_id}",
            json={"state": "closed"},
        )
        return response.json()

    async def add_issues_to_sprint(
        self, sprint_id: int, issue_keys: list[str]
    ) -> None:
        await self._request(
            "POST",
            f"/rest/agile/1.0/sprint/{sprint_id}/issue",
            json={"issues": issue_keys},
        )

    # --- Custom Fields ---

    async def get_custom_fields(self) -> list[dict]:
        response = await self._request("GET", "/rest/api/3/field")
        return response.json()

    async def create_custom_field(
        self, name: str, field_type: str
    ) -> dict:
        payload = {"name": name, "type": field_type, "searcherKey": ""}
        response = await self._request(
            "POST", "/rest/api/3/field", json=payload
        )
        return response.json()

    async def get_field_id_by_name(self, name: str) -> str | None:
        fields = await self.get_custom_fields()
        for field in fields:
            if field.get("name") == name:
                return field["id"]
        return None

    # --- Screens ---

    async def get_screens(self) -> list[dict]:
        """List all screens."""
        response = await self._request(
            "GET", "/rest/api/3/screens", params={"maxResults": 100}
        )
        return response.json().get("values", [])

    async def add_field_to_screen(
        self, screen_id: int, tab_id: int, field_id: str
    ) -> bool:
        """Add a field to a screen tab. Returns True if added."""
        try:
            await self._request(
                "POST",
                f"/rest/api/3/screens/{screen_id}/tabs/{tab_id}/fields",
                json={"fieldId": field_id},
            )
            return True
        except JiraConnectionError:
            return False

    async def get_screen_tabs(self, screen_id: int) -> list[dict]:
        """Get tabs for a screen."""
        response = await self._request(
            "GET", f"/rest/api/3/screens/{screen_id}/tabs"
        )
        data = response.json()
        return data if isinstance(data, list) else []

    async def add_field_to_all_screens(self, field_id: str) -> int:
        """Add a custom field to all screens. Returns count added."""
        screens = await self.get_screens()
        added = 0
        for screen in screens:
            tabs = await self.get_screen_tabs(screen["id"])
            if tabs:
                if await self.add_field_to_screen(
                    screen["id"], tabs[0]["id"], field_id
                ):
                    added += 1
        return added

    # --- Statuses & Transitions ---

    async def get_project_statuses(
        self, project_key: str
    ) -> list[dict]:
        response = await self._request(
            "GET", f"/rest/api/3/project/{project_key}/statuses"
        )
        data = response.json()
        statuses = []
        for issue_type_statuses in data:
            statuses.extend(issue_type_statuses.get("statuses", []))
        return statuses

    async def get_issue_transitions(
        self, issue_key: str
    ) -> list[dict]:
        response = await self._request(
            "GET", f"/rest/api/3/issue/{issue_key}/transitions"
        )
        return response.json().get("transitions", [])

    async def transition_issue(
        self, issue_key: str, transition_id: str
    ) -> None:
        await self._request(
            "POST",
            f"/rest/api/3/issue/{issue_key}/transitions",
            json={"transition": {"id": transition_id}},
        )

    # --- Issues ---

    async def create_issue(
        self,
        project_key: str,
        issue_type: str,
        summary: str,
        fields: dict,
    ) -> dict:
        payload = {
            "fields": {
                "project": {"key": project_key},
                "issuetype": {"name": issue_type},
                "summary": summary,
                **fields,
            }
        }
        response = await self._request(
            "POST", "/rest/api/3/issue", json=payload
        )
        return response.json()

    async def set_estimation(
        self, issue_key: str, board_id: int, value: float,
    ) -> None:
        """Set story points via the Agile estimation API.

        This bypasses screen restrictions that block setting custom fields
        through the standard issue create/update endpoints.
        """
        await self._request(
            "PUT",
            f"/rest/agile/1.0/issue/{issue_key}/estimation",
            params={"boardId": board_id},
            json={"value": value},
        )

    async def update_issue(self, issue_key: str, fields: dict) -> None:
        await self._request(
            "PUT",
            f"/rest/api/3/issue/{issue_key}",
            json={"fields": fields},
        )

    async def get_issue(self, issue_key: str) -> dict:
        response = await self._request(
            "GET", f"/rest/api/3/issue/{issue_key}"
        )
        return response.json()

    async def add_comment(self, issue_key: str, body: str) -> dict:
        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": body}],
                    }
                ],
            }
        }
        response = await self._request(
            "POST",
            f"/rest/api/3/issue/{issue_key}/comment",
            json=payload,
        )
        return response.json()

    async def add_to_sprint(
        self, issue_key: str, sprint_id: int
    ) -> None:
        await self.add_issues_to_sprint(sprint_id, [issue_key])

    # --- Issue Links ---

    async def create_issue_link(
        self, link_type: str, inward_key: str, outward_key: str
    ) -> None:
        payload = {
            "type": {"name": link_type},
            "inwardIssue": {"key": inward_key},
            "outwardIssue": {"key": outward_key},
        }
        await self._request(
            "POST", "/rest/api/3/issueLink", json=payload
        )

    async def get_issue_link_types(self) -> list[dict]:
        response = await self._request(
            "GET", "/rest/api/3/issueLinkType"
        )
        return response.json().get("issueLinkTypes", [])

    # --- Search ---

    async def search_issues(
        self, jql: str, fields: list[str] | None = None, max_results: int = 50
    ) -> list[dict]:
        """Search issues using JQL (v3 search/jql endpoint)."""
        params: dict = {"jql": jql, "maxResults": max_results}
        if fields:
            params["fields"] = ",".join(fields)
        response = await self._request(
            "GET", "/rest/api/3/search/jql", params=params,
        )
        return response.json().get("issues", [])

    async def delete_issue(self, issue_key: str) -> None:
        """Delete an issue."""
        await self._request(
            "DELETE", f"/rest/api/3/issue/{issue_key}"
        )

    # --- Sprint management ---

    async def get_sprint(self, sprint_id: int) -> dict:
        """Get sprint details by ID."""
        response = await self._request(
            "GET", f"/rest/agile/1.0/sprint/{sprint_id}"
        )
        return response.json()

    async def get_sprint_issues(
        self, sprint_id: int, max_results: int = 50
    ) -> list[dict]:
        """Get issues in a sprint."""
        response = await self._request(
            "GET",
            f"/rest/agile/1.0/sprint/{sprint_id}/issue",
            params={"maxResults": max_results},
        )
        return response.json().get("issues", [])

    async def move_issues_to_backlog(self, issue_keys: list[str]) -> None:
        """Remove issues from their current sprint (move to backlog)."""
        await self._request(
            "POST",
            "/rest/agile/1.0/backlog/issue",
            json={"issues": issue_keys},
        )

    async def get_board_sprints(
        self, board_id: int, state: str | None = None
    ) -> list[dict]:
        """Get sprints for a board, optionally filtered by state."""
        params = {}
        if state:
            params["state"] = state
        response = await self._request(
            "GET",
            f"/rest/agile/1.0/board/{board_id}/sprint",
            params=params,
        )
        return response.json().get("values", [])
