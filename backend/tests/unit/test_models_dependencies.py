import pytest
from sqlalchemy.exc import IntegrityError

from app.models.cross_team_dependency import CrossTeamDependency
from app.models.organization import Organization
from app.models.team import Team


def _create_two_teams(session):
    org = Organization(name="Org")
    session.add(org)
    session.commit()
    team_a = Team(organization_id=org.id, name="Alpha", jira_project_key="ALPHA")
    team_b = Team(organization_id=org.id, name="Beta", jira_project_key="BETA")
    session.add_all([team_a, team_b])
    session.commit()
    return team_a, team_b


class TestCrossTeamDependency:
    def test_creates_with_required_fields(self, session):
        team_a, team_b = _create_two_teams(session)
        dep = CrossTeamDependency(
            source_team_id=team_a.id,
            target_team_id=team_b.id,
            dependency_type="blocks",
        )
        session.add(dep)
        session.commit()
        assert dep.id is not None
        assert dep.dependency_type == "blocks"

    def test_unique_constraint_on_source_target_type(self, session):
        team_a, team_b = _create_two_teams(session)
        session.add(CrossTeamDependency(
            source_team_id=team_a.id,
            target_team_id=team_b.id,
            dependency_type="blocks",
        ))
        session.commit()
        session.add(CrossTeamDependency(
            source_team_id=team_a.id,
            target_team_id=team_b.id,
            dependency_type="blocks",
        ))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_same_teams_different_type_allowed(self, session):
        team_a, team_b = _create_two_teams(session)
        session.add(CrossTeamDependency(
            source_team_id=team_a.id,
            target_team_id=team_b.id,
            dependency_type="blocks",
        ))
        session.add(CrossTeamDependency(
            source_team_id=team_a.id,
            target_team_id=team_b.id,
            dependency_type="shared_component",
        ))
        session.commit()
        assert session.query(CrossTeamDependency).count() == 2

    def test_reverse_direction_allowed(self, session):
        team_a, team_b = _create_two_teams(session)
        session.add(CrossTeamDependency(
            source_team_id=team_a.id,
            target_team_id=team_b.id,
            dependency_type="blocks",
        ))
        session.add(CrossTeamDependency(
            source_team_id=team_b.id,
            target_team_id=team_a.id,
            dependency_type="blocks",
        ))
        session.commit()
        assert session.query(CrossTeamDependency).count() == 2

    def test_source_team_relationship(self, session):
        team_a, team_b = _create_two_teams(session)
        dep = CrossTeamDependency(
            source_team_id=team_a.id,
            target_team_id=team_b.id,
            dependency_type="blocks",
        )
        session.add(dep)
        session.commit()
        session.refresh(dep)
        assert dep.source_team.name == "Alpha"

    def test_target_team_relationship(self, session):
        team_a, team_b = _create_two_teams(session)
        dep = CrossTeamDependency(
            source_team_id=team_a.id,
            target_team_id=team_b.id,
            dependency_type="blocks",
        )
        session.add(dep)
        session.commit()
        session.refresh(dep)
        assert dep.target_team.name == "Beta"

    def test_timestamps_auto_set(self, session):
        team_a, team_b = _create_two_teams(session)
        dep = CrossTeamDependency(
            source_team_id=team_a.id,
            target_team_id=team_b.id,
            dependency_type="blocks",
        )
        session.add(dep)
        session.commit()
        assert dep.created_at is not None
        assert dep.updated_at is not None
