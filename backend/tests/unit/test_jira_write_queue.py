from unittest.mock import AsyncMock, MagicMock

import pytest

from app.integrations.exceptions import JiraRateLimitError
from app.integrations.jira_write_queue import (
    OPERATION_PRIORITY,
    JiraWriteQueue,
)
from app.models.jira_write_queue_entry import JiraWriteQueueEntry
from app.models.organization import Organization
from app.models.team import Team


def _create_team(session):
    org = Organization(name="Test Org")
    session.add(org)
    session.flush()
    team = Team(
        organization_id=org.id,
        name="Alpha",
        jira_project_key="ALPHA",
    )
    session.add(team)
    session.flush()
    return team


@pytest.fixture
def mock_jira_client():
    client = AsyncMock()
    client.create_issue = AsyncMock(
        return_value={"key": "ALPHA-1", "id": "10001"}
    )
    client.update_issue = AsyncMock()
    client.transition_issue = AsyncMock()
    client.add_comment = AsyncMock(return_value={"id": "1"})
    client.create_issue_link = AsyncMock()
    client.add_issues_to_sprint = AsyncMock()
    return client


@pytest.fixture
def mock_health():
    health = MagicMock()
    health.status = "ONLINE"
    return health


@pytest.fixture
def queue(session, mock_jira_client, mock_health):
    session_factory = MagicMock(return_value=session)
    return JiraWriteQueue(session_factory, mock_jira_client, mock_health)


class TestEnqueue:
    def test_creates_pending_entry(self, session, queue):
        team = _create_team(session)
        queue.enqueue(
            team_id=team.id,
            operation_type="CREATE_ISSUE",
            payload={"summary": "test"},
        )
        entries = session.query(JiraWriteQueueEntry).all()
        assert len(entries) == 1
        assert entries[0].status == "PENDING"
        assert entries[0].operation_type == "CREATE_ISSUE"

    def test_assigns_correct_priority(self, session, queue):
        team = _create_team(session)
        queue.enqueue(
            team_id=team.id,
            operation_type="CREATE_ISSUE",
            payload={},
        )
        entry = session.query(JiraWriteQueueEntry).first()
        assert entry.priority == OPERATION_PRIORITY["CREATE_ISSUE"]

    def test_accepts_optional_issue_id(self, session, queue):
        from app.models.issue import Issue

        team = _create_team(session)
        issue = Issue(
            team_id=team.id,
            issue_type="Story",
            summary="Test",
            status="backlog",
        )
        session.add(issue)
        session.flush()
        queue.enqueue(
            team_id=team.id,
            operation_type="UPDATE_ISSUE",
            payload={},
            issue_id=issue.id,
        )
        entry = session.query(JiraWriteQueueEntry).first()
        assert entry.issue_id == issue.id


class TestPriorityOrder:
    def test_create_issue_highest_priority(self):
        assert OPERATION_PRIORITY["CREATE_ISSUE"] == 1

    def test_add_to_sprint_before_transition(self):
        assert OPERATION_PRIORITY["ADD_TO_SPRINT"] < OPERATION_PRIORITY["TRANSITION_ISSUE"]

    def test_comment_lower_than_transition(self):
        assert OPERATION_PRIORITY["ADD_COMMENT"] > OPERATION_PRIORITY["TRANSITION_ISSUE"]


class TestProcessOne:
    @pytest.mark.asyncio
    async def test_marks_done_on_success(self, session, queue):
        team = _create_team(session)
        queue.enqueue(
            team_id=team.id,
            operation_type="ADD_COMMENT",
            payload={"issue_key": "ALPHA-1", "body": "Hello"},
        )
        entry = session.query(JiraWriteQueueEntry).first()
        await queue.process_one(entry)
        session.refresh(entry)
        assert entry.status == "DONE"
        assert entry.processed_at is not None

    @pytest.mark.asyncio
    async def test_marks_failed_on_error(self, session, queue, mock_jira_client):
        mock_jira_client.add_comment.side_effect = Exception("Boom")
        team = _create_team(session)
        queue.enqueue(
            team_id=team.id,
            operation_type="ADD_COMMENT",
            payload={"issue_key": "ALPHA-1", "body": "Hello"},
        )
        entry = session.query(JiraWriteQueueEntry).first()
        await queue.process_one(entry)
        session.refresh(entry)
        assert entry.status == "FAILED"
        assert entry.attempts == 1
        assert "Boom" in entry.last_error

    @pytest.mark.asyncio
    async def test_rate_limit_returns_retry_after(
        self, session, queue, mock_jira_client
    ):
        mock_jira_client.add_comment.side_effect = JiraRateLimitError(45.0)
        team = _create_team(session)
        queue.enqueue(
            team_id=team.id,
            operation_type="ADD_COMMENT",
            payload={"issue_key": "ALPHA-1", "body": "Hello"},
        )
        entry = session.query(JiraWriteQueueEntry).first()
        retry_after = await queue.process_one(entry)
        assert retry_after == 45.0
        session.refresh(entry)
        assert entry.status == "PENDING"


class TestGetPendingBatch:
    def test_returns_ordered_by_priority_then_created(self, session, queue):
        team = _create_team(session)
        queue.enqueue(
            team_id=team.id,
            operation_type="ADD_COMMENT",
            payload={},
        )
        queue.enqueue(
            team_id=team.id,
            operation_type="CREATE_ISSUE",
            payload={},
        )
        batch = queue.get_pending_batch()
        assert batch[0].operation_type == "CREATE_ISSUE"
        assert batch[1].operation_type == "ADD_COMMENT"


class TestRecoveryCollapse:
    @pytest.mark.asyncio
    async def test_collapses_pending_for_same_issue(self, session, queue):
        from app.models.issue import Issue

        team = _create_team(session)
        issue = Issue(
            team_id=team.id,
            issue_type="Story",
            summary="Test",
            status="backlog",
        )
        session.add(issue)
        session.flush()

        queue.enqueue(
            team_id=team.id,
            operation_type="TRANSITION_ISSUE",
            payload={"issue_key": "ALPHA-1", "transition_id": "31"},
            issue_id=issue.id,
        )
        queue.enqueue(
            team_id=team.id,
            operation_type="TRANSITION_ISSUE",
            payload={"issue_key": "ALPHA-1", "transition_id": "41"},
            issue_id=issue.id,
        )
        queue.enqueue(
            team_id=team.id,
            operation_type="ADD_COMMENT",
            payload={"issue_key": "ALPHA-1", "body": "WIP"},
            issue_id=issue.id,
        )

        await queue.run_recovery()

        entries = (
            session.query(JiraWriteQueueEntry)
            .filter(JiraWriteQueueEntry.issue_id == issue.id)
            .all()
        )
        skipped = [e for e in entries if e.status == "SKIPPED"]
        assert len(skipped) >= 2

    @pytest.mark.asyncio
    async def test_skips_recovery_when_no_pending(self, session, queue):
        await queue.run_recovery()


class TestRetryFailed:
    def test_resets_failed_to_pending(self, session, queue):
        team = _create_team(session)
        queue.enqueue(
            team_id=team.id,
            operation_type="CREATE_ISSUE",
            payload={},
        )
        entry = session.query(JiraWriteQueueEntry).first()
        entry.status = "FAILED"
        entry.attempts = 3
        session.commit()

        count = queue.retry_failed()
        session.refresh(entry)
        assert entry.status == "PENDING"
        assert entry.attempts == 0
        assert count == 1
