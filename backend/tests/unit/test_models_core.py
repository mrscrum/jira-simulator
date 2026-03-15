import pytest
from sqlalchemy.exc import IntegrityError

from app.models.member import Member
from app.models.organization import Organization
from app.models.team import Team


class TestOrganization:
    def test_creates_with_required_fields(self, session):
        org = Organization(name="Test Org")
        session.add(org)
        session.commit()
        assert org.id is not None
        assert org.name == "Test Org"

    def test_description_is_nullable(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.commit()
        assert org.description is None

    def test_name_is_unique(self, session):
        session.add(Organization(name="Unique"))
        session.commit()
        session.add(Organization(name="Unique"))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_name_is_required(self, session):
        org = Organization()
        session.add(org)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_has_created_at(self, session):
        org = Organization(name="Timestamped")
        session.add(org)
        session.commit()
        assert org.created_at is not None

    def test_has_updated_at(self, session):
        org = Organization(name="Timestamped")
        session.add(org)
        session.commit()
        assert org.updated_at is not None

    def test_teams_relationship(self, session):
        org = Organization(name="With Teams")
        session.add(org)
        session.commit()
        team = Team(
            organization_id=org.id,
            name="Team A",
            jira_project_key="TA",
        )
        session.add(team)
        session.commit()
        session.refresh(org)
        assert len(org.teams) == 1
        assert org.teams[0].name == "Team A"


class TestTeam:
    def test_creates_with_required_fields(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.commit()
        team = Team(
            organization_id=org.id,
            name="Backend",
            jira_project_key="BE",
        )
        session.add(team)
        session.commit()
        assert team.id is not None
        assert team.name == "Backend"
        assert team.jira_project_key == "BE"

    def test_jira_project_key_is_unique(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.commit()
        session.add(Team(organization_id=org.id, name="T1", jira_project_key="DUP"))
        session.commit()
        session.add(Team(organization_id=org.id, name="T2", jira_project_key="DUP"))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_is_active_defaults_to_true(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.commit()
        team = Team(organization_id=org.id, name="T", jira_project_key="T1")
        session.add(team)
        session.commit()
        assert team.is_active is True

    def test_jira_board_id_is_nullable(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.commit()
        team = Team(organization_id=org.id, name="T", jira_project_key="T1")
        session.add(team)
        session.commit()
        assert team.jira_board_id is None

    def test_organization_relationship(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.commit()
        team = Team(organization_id=org.id, name="T", jira_project_key="T1")
        session.add(team)
        session.commit()
        session.refresh(team)
        assert team.organization.name == "Org"


class TestMember:
    def test_creates_with_required_fields(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.commit()
        team = Team(organization_id=org.id, name="T", jira_project_key="T1")
        session.add(team)
        session.commit()
        member = Member(team_id=team.id, name="Alice", role="DEV")
        session.add(member)
        session.commit()
        assert member.id is not None
        assert member.name == "Alice"
        assert member.role == "DEV"

    def test_daily_capacity_defaults_to_six(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.commit()
        team = Team(organization_id=org.id, name="T", jira_project_key="T1")
        session.add(team)
        session.commit()
        member = Member(team_id=team.id, name="Bob", role="QA")
        session.add(member)
        session.commit()
        assert member.daily_capacity_hours == 6.0

    def test_max_concurrent_wip_defaults_to_three(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.commit()
        team = Team(organization_id=org.id, name="T", jira_project_key="T1")
        session.add(team)
        session.commit()
        member = Member(team_id=team.id, name="Carol", role="PO")
        session.add(member)
        session.commit()
        assert member.max_concurrent_wip == 3

    def test_is_active_defaults_to_true(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.commit()
        team = Team(organization_id=org.id, name="T", jira_project_key="T1")
        session.add(team)
        session.commit()
        member = Member(team_id=team.id, name="Dave", role="SM")
        session.add(member)
        session.commit()
        assert member.is_active is True

    def test_team_relationship(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.commit()
        team = Team(organization_id=org.id, name="Team X", jira_project_key="TX")
        session.add(team)
        session.commit()
        member = Member(team_id=team.id, name="Eve", role="DEV")
        session.add(member)
        session.commit()
        session.refresh(member)
        assert member.team.name == "Team X"

    def test_team_members_relationship(self, session):
        org = Organization(name="Org")
        session.add(org)
        session.commit()
        team = Team(organization_id=org.id, name="T", jira_project_key="T1")
        session.add(team)
        session.commit()
        session.add(Member(team_id=team.id, name="A", role="DEV"))
        session.add(Member(team_id=team.id, name="B", role="QA"))
        session.commit()
        session.refresh(team)
        assert len(team.members) == 2
