from app.models.dysfunction_config import DysfunctionConfig
from app.models.organization import Organization
from app.models.team import Team


def _create_team(session):
    org = Organization(name="Org")
    session.add(org)
    session.commit()
    team = Team(organization_id=org.id, name="T", jira_project_key="T1")
    session.add(team)
    session.commit()
    return team


class TestDysfunctionConfigDetailFields:
    def test_low_quality_detail_defaults(self, session):
        team = _create_team(session)
        config = DysfunctionConfig(team_id=team.id)
        session.add(config)
        session.commit()
        assert config.low_quality_ba_po_touch_min == 1.5
        assert config.low_quality_ba_po_touch_max == 2.5
        assert config.low_quality_dev_touch_min == 1.2
        assert config.low_quality_dev_touch_max == 1.8
        assert config.low_quality_qa_touch_min == 1.5
        assert config.low_quality_qa_touch_max == 3.0
        assert config.low_quality_ba_cycle_back_pct == 0.40
        assert config.low_quality_qa_cycle_back_pct == 0.50
        assert config.low_quality_bug_injection_boost_pct == 0.30
        assert config.low_quality_re_estimation_boost_pct == 0.40

    def test_scope_add_detail_defaults(self, session):
        team = _create_team(session)
        config = DysfunctionConfig(team_id=team.id)
        session.add(config)
        session.commit()
        assert config.scope_add_capacity_tax_min_pct == 0.85
        assert config.scope_add_capacity_tax_max_pct == 0.95
        assert config.scope_add_touch_multiplier_min == 1.1
        assert config.scope_add_touch_multiplier_max == 1.3
        assert config.scope_add_tax_duration_days_min == 1.0
        assert config.scope_add_tax_duration_days_max == 2.0

    def test_blocking_dependency_detail_defaults(self, session):
        team = _create_team(session)
        config = DysfunctionConfig(team_id=team.id)
        session.add(config)
        session.commit()
        assert config.blocking_dep_escalation_wait_hours == 24.0
        assert config.blocking_dep_blocker_focus_multiplier == 0.8

    def test_dark_teammate_detail_defaults(self, session):
        team = _create_team(session)
        config = DysfunctionConfig(team_id=team.id)
        session.add(config)
        session.commit()
        assert config.dark_teammate_duration_days_min == 2.0
        assert config.dark_teammate_duration_days_max == 5.0
        assert config.dark_teammate_reassignment_ramp_pct == 0.70

    def test_re_estimation_detail_defaults(self, session):
        team = _create_team(session)
        config = DysfunctionConfig(team_id=team.id)
        session.add(config)
        session.commit()
        assert config.re_estimation_sp_multiplier_min == 1.5
        assert config.re_estimation_sp_multiplier_max == 2.5
        assert config.re_estimation_descope_probability_pct == 0.70

    def test_bug_injection_detail_defaults(self, session):
        team = _create_team(session)
        config = DysfunctionConfig(team_id=team.id)
        session.add(config)
        session.commit()
        assert config.bug_injection_sp_weight_1 == 0.5
        assert config.bug_injection_sp_weight_2 == 0.3
        assert config.bug_injection_sp_weight_3 == 0.2
        assert config.bug_injection_interruption_tax_multiplier == 1.1

    def test_detail_fields_are_writable(self, session):
        team = _create_team(session)
        config = DysfunctionConfig(
            team_id=team.id,
            low_quality_ba_po_touch_min=2.0,
            blocking_dep_escalation_wait_hours=48.0,
            bug_injection_sp_weight_1=0.6,
        )
        session.add(config)
        session.commit()
        assert config.low_quality_ba_po_touch_min == 2.0
        assert config.blocking_dep_escalation_wait_hours == 48.0
        assert config.bug_injection_sp_weight_1 == 0.6
