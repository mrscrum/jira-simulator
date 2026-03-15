import pytest
from sqlalchemy.exc import IntegrityError

from app.models.jira_config import JiraConfig
from app.models.jira_issue_link import JiraIssueLink
from app.models.jira_issue_map import JiraIssueMap
from app.models.jira_write_queue_entry import JiraWriteQueueEntry
from app.models.organization import Organization
from app.models.team import Team


def _create_team(session):
    org = Organization(name="Test Org")
    session.add(org)
    session.flush()
    team = Team(
        organization_id=org.id,
        name="Alpha Squad",
        jira_project_key="ALPHA",
    )
    session.add(team)
    session.flush()
    return team


def _create_issue(session, team):
    from app.models.issue import Issue

    issue = Issue(
        team_id=team.id,
        issue_type="Story",
        summary="Test issue",
        status="backlog",
    )
    session.add(issue)
    session.flush()
    return issue


class TestJiraConfig:
    def test_creates_with_key_and_value(self, session):
        config = JiraConfig(key="field_id_sim_assignee", value="customfield_10001")
        session.add(config)
        session.commit()
        assert config.key == "field_id_sim_assignee"
        assert config.value == "customfield_10001"

    def test_key_is_primary_key(self, session):
        config = JiraConfig(key="test_key", value="val1")
        session.add(config)
        session.commit()
        config2 = JiraConfig(key="test_key", value="val2")
        session.add(config2)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_value_is_required(self, session):
        config = JiraConfig(key="no_value")
        session.add(config)
        with pytest.raises(IntegrityError):
            session.commit()


class TestJiraWriteQueueEntry:
    def test_creates_with_required_fields(self, session):
        team = _create_team(session)
        entry = JiraWriteQueueEntry(
            team_id=team.id,
            operation_type="CREATE_ISSUE",
            payload={"summary": "test"},
        )
        session.add(entry)
        session.commit()
        assert entry.id is not None
        assert entry.status == "PENDING"
        assert entry.priority == 5
        assert entry.attempts == 0

    def test_status_defaults_to_pending(self, session):
        team = _create_team(session)
        entry = JiraWriteQueueEntry(
            team_id=team.id,
            operation_type="UPDATE_ISSUE",
            payload={},
        )
        session.add(entry)
        session.commit()
        assert entry.status == "PENDING"

    def test_priority_defaults_to_five(self, session):
        team = _create_team(session)
        entry = JiraWriteQueueEntry(
            team_id=team.id,
            operation_type="TRANSITION_ISSUE",
            payload={},
        )
        session.add(entry)
        session.commit()
        assert entry.priority == 5

    def test_issue_id_is_nullable(self, session):
        team = _create_team(session)
        entry = JiraWriteQueueEntry(
            team_id=team.id,
            operation_type="COMPLETE_SPRINT",
            payload={},
        )
        session.add(entry)
        session.commit()
        assert entry.issue_id is None

    def test_issue_id_foreign_key(self, session):
        team = _create_team(session)
        issue = _create_issue(session, team)
        entry = JiraWriteQueueEntry(
            team_id=team.id,
            issue_id=issue.id,
            operation_type="CREATE_ISSUE",
            payload={"summary": "test"},
        )
        session.add(entry)
        session.commit()
        assert entry.issue_id == issue.id

    def test_last_error_is_nullable(self, session):
        team = _create_team(session)
        entry = JiraWriteQueueEntry(
            team_id=team.id,
            operation_type="CREATE_ISSUE",
            payload={},
        )
        session.add(entry)
        session.commit()
        assert entry.last_error is None

    def test_processed_at_is_nullable(self, session):
        team = _create_team(session)
        entry = JiraWriteQueueEntry(
            team_id=team.id,
            operation_type="CREATE_ISSUE",
            payload={},
        )
        session.add(entry)
        session.commit()
        assert entry.processed_at is None

    def test_has_created_at(self, session):
        team = _create_team(session)
        entry = JiraWriteQueueEntry(
            team_id=team.id,
            operation_type="CREATE_ISSUE",
            payload={},
        )
        session.add(entry)
        session.commit()
        assert entry.created_at is not None


class TestJiraIssueMap:
    def test_creates_with_required_fields(self, session):
        team = _create_team(session)
        issue = _create_issue(session, team)
        mapping = JiraIssueMap(
            issue_id=issue.id,
            jira_key="ALPHA-42",
            jira_id="10042",
        )
        session.add(mapping)
        session.commit()
        assert mapping.issue_id == issue.id
        assert mapping.jira_key == "ALPHA-42"
        assert mapping.jira_id == "10042"

    def test_issue_id_is_primary_key(self, session):
        team = _create_team(session)
        issue = _create_issue(session, team)
        session.add(JiraIssueMap(issue_id=issue.id, jira_key="A-1", jira_id="1"))
        session.commit()
        session.add(JiraIssueMap(issue_id=issue.id, jira_key="A-2", jira_id="2"))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_jira_key_is_unique(self, session):
        team = _create_team(session)
        issue1 = _create_issue(session, team)
        issue2 = _create_issue(session, team)
        session.add(JiraIssueMap(issue_id=issue1.id, jira_key="ALPHA-1", jira_id="1"))
        session.commit()
        session.add(JiraIssueMap(issue_id=issue2.id, jira_key="ALPHA-1", jira_id="2"))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_has_created_at(self, session):
        team = _create_team(session)
        issue = _create_issue(session, team)
        mapping = JiraIssueMap(
            issue_id=issue.id,
            jira_key="ALPHA-1",
            jira_id="1",
        )
        session.add(mapping)
        session.commit()
        assert mapping.created_at is not None


class TestJiraIssueLink:
    def test_creates_with_required_fields(self, session):
        team = _create_team(session)
        issue1 = _create_issue(session, team)
        issue2 = _create_issue(session, team)
        link = JiraIssueLink(
            from_issue_id=issue1.id,
            to_issue_id=issue2.id,
            link_type="blocks",
        )
        session.add(link)
        session.commit()
        assert link.id is not None
        assert link.link_type == "blocks"
        assert link.status == "PENDING"

    def test_status_defaults_to_pending(self, session):
        team = _create_team(session)
        issue1 = _create_issue(session, team)
        issue2 = _create_issue(session, team)
        link = JiraIssueLink(
            from_issue_id=issue1.id,
            to_issue_id=issue2.id,
            link_type="relates",
        )
        session.add(link)
        session.commit()
        assert link.status == "PENDING"

    def test_jira_link_id_is_nullable(self, session):
        team = _create_team(session)
        issue1 = _create_issue(session, team)
        issue2 = _create_issue(session, team)
        link = JiraIssueLink(
            from_issue_id=issue1.id,
            to_issue_id=issue2.id,
            link_type="blocks",
        )
        session.add(link)
        session.commit()
        assert link.jira_link_id is None


class TestTeamJiraBootstrapFields:
    def test_jira_bootstrapped_defaults_to_false(self, session):
        team = _create_team(session)
        assert team.jira_bootstrapped is False

    def test_jira_bootstrap_warnings_is_nullable(self, session):
        team = _create_team(session)
        assert team.jira_bootstrap_warnings is None

    def test_jira_bootstrapped_at_is_nullable(self, session):
        team = _create_team(session)
        assert team.jira_bootstrapped_at is None

    def test_can_set_bootstrap_fields(self, session):
        from datetime import UTC, datetime

        team = _create_team(session)
        team.jira_bootstrapped = True
        team.jira_bootstrap_warnings = '["Missing status: QA"]'
        team.jira_bootstrapped_at = datetime.now(UTC)
        session.commit()
        session.refresh(team)
        assert team.jira_bootstrapped is True
        assert "Missing status" in team.jira_bootstrap_warnings
        assert team.jira_bootstrapped_at is not None
