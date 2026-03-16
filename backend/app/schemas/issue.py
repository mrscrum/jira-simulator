from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IssueBase(BaseModel):
    issue_type: str
    summary: str
    description: str | None = None
    story_points: int | None = None
    priority: str = "Medium"


class IssueCreate(IssueBase):
    team_id: int
    jira_issue_key: str | None = None
    jira_issue_id: str | None = None
    current_workflow_step_id: int | None = None
    current_worker_id: int | None = None
    jira_assignee_id: int | None = None
    jira_reporter_id: int | None = None
    sprint_id: int | None = None


class IssueRead(IssueBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    jira_issue_key: str | None = None
    jira_issue_id: str | None = None
    current_workflow_step_id: int | None = None
    current_worker_id: int | None = None
    jira_assignee_id: int | None = None
    jira_reporter_id: int | None = None
    touch_time_remaining_hours: float = 0.0
    wait_time_accumulated_hours: float = 0.0
    total_cycle_time_hours: float = 0.0
    sprint_id: int | None = None
    is_blocked: bool = False
    blocked_by_issue_id: int | None = None
    dysfunction_flags: str | None = None
    status: str = "backlog"
    completed_at: datetime | None = None
    backlog_priority: int | None = None
    carried_over: bool = False
    descoped: bool = False
    split_from_id: int | None = None
    created_at: datetime
    updated_at: datetime


class IssueUpdate(BaseModel):
    summary: str | None = None
    description: str | None = None
    story_points: int | None = None
    priority: str | None = None
    current_workflow_step_id: int | None = None
    current_worker_id: int | None = None
    touch_time_remaining_hours: float | None = None
    wait_time_accumulated_hours: float | None = None
    total_cycle_time_hours: float | None = None
    sprint_id: int | None = None
    is_blocked: bool | None = None
    blocked_by_issue_id: int | None = None
    dysfunction_flags: str | None = None
    status: str | None = None
    completed_at: datetime | None = None
    backlog_priority: int | None = None
    carried_over: bool | None = None
    descoped: bool | None = None
    split_from_id: int | None = None
