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
