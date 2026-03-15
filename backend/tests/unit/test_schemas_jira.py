from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.jira import (
    BootstrapStatusResponse,
    JiraHealthResponse,
    JiraStatus,
    QueueStatusResponse,
)


class TestJiraStatus:
    def test_valid(self):
        status = JiraStatus(name="In Progress", category="indeterminate")
        assert status.name == "In Progress"
        assert status.category == "indeterminate"

    def test_name_required(self):
        with pytest.raises(ValidationError):
            JiraStatus(category="done")

    def test_category_required(self):
        with pytest.raises(ValidationError):
            JiraStatus(name="Done")


class TestBootstrapStatusResponse:
    def test_valid_complete(self):
        response = BootstrapStatusResponse(
            bootstrapped=True,
            warnings=[],
            board_id=42,
            custom_field_ids={"sim_assignee": "cf_10001"},
            last_run=datetime(2026, 3, 15, tzinfo=UTC),
        )
        assert response.bootstrapped is True
        assert response.board_id == 42

    def test_valid_minimal(self):
        response = BootstrapStatusResponse(
            bootstrapped=False,
            warnings=[],
            board_id=None,
            custom_field_ids={},
            last_run=None,
        )
        assert response.bootstrapped is False

    def test_warnings_list(self):
        response = BootstrapStatusResponse(
            bootstrapped=True,
            warnings=["Missing status: QA", "Missing status: Review"],
            board_id=1,
            custom_field_ids={},
            last_run=None,
        )
        assert len(response.warnings) == 2


class TestJiraHealthResponse:
    def test_valid_online(self):
        now = datetime.now(UTC)
        response = JiraHealthResponse(
            status="ONLINE",
            last_checked=now,
            last_online=now,
            consecutive_failures=0,
            outage_start=None,
        )
        assert response.status == "ONLINE"

    def test_valid_offline(self):
        now = datetime.now(UTC)
        response = JiraHealthResponse(
            status="OFFLINE",
            last_checked=now,
            last_online=now,
            consecutive_failures=3,
            outage_start=now,
        )
        assert response.status == "OFFLINE"
        assert response.consecutive_failures == 3

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            JiraHealthResponse(
                status="UNKNOWN",
                last_checked=None,
                last_online=None,
                consecutive_failures=0,
                outage_start=None,
            )


class TestQueueStatusResponse:
    def test_valid(self):
        response = QueueStatusResponse(
            pending=10,
            in_flight=2,
            done=100,
            failed=3,
            skipped=5,
            total=120,
        )
        assert response.pending == 10
        assert response.total == 120

    def test_all_zeros(self):
        response = QueueStatusResponse(
            pending=0,
            in_flight=0,
            done=0,
            failed=0,
            skipped=0,
            total=0,
        )
        assert response.total == 0
