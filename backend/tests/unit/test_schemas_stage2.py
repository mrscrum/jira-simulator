from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.cross_team_dependency import (
    CrossTeamDependencyCreate,
    CrossTeamDependencyRead,
)
from app.schemas.dysfunction_config import (
    DysfunctionConfigRead,
    DysfunctionConfigUpdate,
)


class TestCrossTeamDependencySchemas:
    def test_create_with_valid_data(self):
        schema = CrossTeamDependencyCreate(
            source_team_id=1,
            target_team_id=2,
            dependency_type="blocks",
        )
        assert schema.source_team_id == 1
        assert schema.dependency_type == "blocks"

    def test_create_requires_source_team_id(self):
        with pytest.raises(ValidationError):
            CrossTeamDependencyCreate(
                target_team_id=2,
                dependency_type="blocks",
            )

    def test_create_requires_target_team_id(self):
        with pytest.raises(ValidationError):
            CrossTeamDependencyCreate(
                source_team_id=1,
                dependency_type="blocks",
            )

    def test_create_requires_dependency_type(self):
        with pytest.raises(ValidationError):
            CrossTeamDependencyCreate(
                source_team_id=1,
                target_team_id=2,
            )

    def test_read_includes_id_and_timestamps(self):
        now = datetime.now(UTC)
        schema = CrossTeamDependencyRead(
            id=1,
            source_team_id=1,
            target_team_id=2,
            dependency_type="blocks",
            created_at=now,
            updated_at=now,
        )
        assert schema.id == 1


class TestDysfunctionConfigUpdateSchema:
    def test_all_fields_optional(self):
        schema = DysfunctionConfigUpdate()
        assert schema.low_quality_probability is None
        assert schema.low_quality_ba_po_touch_min is None

    def test_partial_update(self):
        schema = DysfunctionConfigUpdate(
            low_quality_probability=0.25,
            low_quality_ba_po_touch_min=2.0,
        )
        assert schema.low_quality_probability == 0.25
        assert schema.low_quality_ba_po_touch_min == 2.0
        assert schema.scope_creep_probability is None


class TestDysfunctionConfigReadWithDetails:
    def test_read_includes_detail_fields(self):
        now = datetime.now(UTC)
        schema = DysfunctionConfigRead(
            id=1,
            team_id=1,
            created_at=now,
            updated_at=now,
        )
        assert schema.low_quality_ba_po_touch_min == 1.5
        assert schema.blocking_dep_escalation_wait_hours == 24.0
        assert schema.bug_injection_sp_weight_1 == 0.5

    def test_read_with_custom_detail_values(self):
        now = datetime.now(UTC)
        schema = DysfunctionConfigRead(
            id=1,
            team_id=1,
            low_quality_ba_po_touch_min=3.0,
            blocking_dep_escalation_wait_hours=48.0,
            created_at=now,
            updated_at=now,
        )
        assert schema.low_quality_ba_po_touch_min == 3.0
        assert schema.blocking_dep_escalation_wait_hours == 48.0
