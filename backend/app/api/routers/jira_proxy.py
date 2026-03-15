from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/jira", tags=["jira"])

SAMPLE_STATUSES = [
    {"name": "To Do", "category": "new"},
    {"name": "In Progress", "category": "indeterminate"},
    {"name": "In Review", "category": "indeterminate"},
    {"name": "QA", "category": "indeterminate"},
    {"name": "Done", "category": "done"},
]


class JiraStatus(BaseModel):
    name: str
    category: str


@router.get(
    "/projects/{project_key}/statuses",
    response_model=list[JiraStatus],
)
def get_project_statuses(project_key: str):
    return SAMPLE_STATUSES
