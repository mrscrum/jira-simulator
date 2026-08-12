"""In-memory fake implementing the public JiraClient methods used by v2 delivery."""

from datetime import datetime

from app.integrations.exceptions import JiraConnectionError


class FakeJiraClient:
    def __init__(self) -> None:
        self.online = True
        self.projects: dict[str, dict] = {}
        self.boards: dict[str, dict] = {}
        self.issues: dict[str, dict] = {}
        self.sprints: dict[int, dict] = {}
        self.project_creates = 0
        self.issue_creates = 0
        self.sprint_creates = 0

    def _available(self) -> None:
        if not self.online:
            raise JiraConnectionError("fake Jira is unavailable")

    async def get_project(self, project_key: str) -> dict | None:
        self._available()
        return self.projects.get(project_key)

    async def create_project(self, key: str, name: str, board_type: str) -> dict:
        self._available()
        self.project_creates += 1
        project = {"id": str(100 + self.project_creates), "key": key, "name": name}
        self.projects[key] = project
        self.boards[key] = {
            "id": 200 + self.project_creates,
            "key": key,
            "name": f"{name} board",
            "type": board_type,
        }
        return project

    async def get_board(self, project_key: str) -> dict | None:
        self._available()
        return self.boards.get(project_key)

    async def search_issues(
        self, jql: str, fields: list[str] | None = None, max_results: int = 50
    ) -> list[dict]:
        self._available()
        del fields
        marker = jql.split('"')[1]
        matches = [
            issue for issue in self.issues.values() if marker in issue["fields"].get("labels", [])
        ]
        return matches[:max_results]

    async def create_issue(
        self, project_key: str, issue_type: str, summary: str, fields: dict
    ) -> dict:
        self._available()
        self.issue_creates += 1
        key = f"{project_key}-{self.issue_creates}"
        issue = {
            "id": str(1_000 + self.issue_creates),
            "key": key,
            "fields": {
                "issuetype": {"name": issue_type},
                "status": {"name": "To Do"},
                "summary": summary,
                **fields,
            },
        }
        self.issues[key] = issue
        return issue

    async def get_board_sprints(self, board_id: int, state: str | None = None) -> list[dict]:
        self._available()
        matches = [
            sprint for sprint in self.sprints.values() if sprint["originBoardId"] == board_id
        ]
        if state is not None:
            matches = [sprint for sprint in matches if sprint["state"] == state]
        return matches

    async def create_sprint(
        self,
        board_id: int,
        name: str,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        self._available()
        self.sprint_creates += 1
        sprint_id = 500 + self.sprint_creates
        sprint = {
            "id": sprint_id,
            "name": name,
            "originBoardId": board_id,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "state": "future",
            "issues": [],
        }
        self.sprints[sprint_id] = sprint
        return sprint

    async def get_sprint(self, sprint_id: int) -> dict:
        self._available()
        return self.sprints[sprint_id]

    async def get_sprint_issues(self, sprint_id: int, max_results: int = 50) -> list[dict]:
        self._available()
        keys = self.sprints[sprint_id]["issues"][:max_results]
        return [self.issues[key] for key in keys]

    async def add_issues_to_sprint(self, sprint_id: int, issue_keys: list[str]) -> None:
        self._available()
        existing = self.sprints[sprint_id]["issues"]
        existing.extend(key for key in issue_keys if key not in existing)

    async def start_sprint(self, sprint_id: int) -> dict:
        self._available()
        self.sprints[sprint_id]["state"] = "active"
        return self.sprints[sprint_id]

    async def complete_sprint(self, sprint_id: int) -> dict:
        self._available()
        self.sprints[sprint_id]["state"] = "closed"
        return self.sprints[sprint_id]

    async def get_issue(self, issue_key: str) -> dict:
        self._available()
        return self.issues[issue_key]

    async def get_issue_transitions(self, issue_key: str) -> list[dict]:
        self._available()
        del issue_key
        names = ("To Do", "Development", "Code Review", "Done", "Cancelled")
        return [
            {"id": str(index), "name": name, "to": {"name": name}}
            for index, name in enumerate(names, start=1)
        ]

    async def transition_issue(self, issue_key: str, transition_id: str) -> None:
        self._available()
        transitions = await self.get_issue_transitions(issue_key)
        target = next(item["to"]["name"] for item in transitions if item["id"] == transition_id)
        self.issues[issue_key]["fields"]["status"] = {"name": target}
