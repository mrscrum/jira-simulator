import ast
import subprocess
import sys
from pathlib import Path
from typing import Protocol

import pytest

from app.v2.domain.live_slice import LedgerPageQuery, ProjectionIntent, ProjectionPageQuery
from app.v2.persistence.unit_of_work import SqlAlchemyV2UnitOfWork
from tests.v2.live_slice_support import create_aggregate, make_tick_commit

V2_TABLE_NAMES = {
    "v2_teams",
    "v2_team_blueprints",
    "v2_runs",
    "v2_team_runtimes",
    "v2_activity_events",
    "v2_ground_truth_records",
    "v2_projection_intents",
    "v2_member_identities",
    "v2_member_availability_overlays",
    "v2_member_business_date_consumption",
    "v2_work_items",
    "v2_work_item_factors",
    "v2_sprints",
    "v2_sprint_scope",
    "v2_status_visits",
    "v2_status_visit_samples",
    "v2_semantic_counters",
    "v2_natural_decision_evaluations",
}
TEAM_MODEL_NAMES = ("V2TeamModel", "V2TeamBlueprintModel", "V2RunModel", "V2TeamRuntimeModel")
LIVE_MODEL_NAMES = (
    "V2ActivityEventModel",
    "V2GroundTruthRecordModel",
    "V2ProjectionIntentModel",
)
SCRUM_MODEL_NAMES = (
    "V2MemberIdentityModel",
    "V2MemberAvailabilityOverlayModel",
    "V2MemberBusinessDateConsumptionModel",
    "V2WorkItemModel",
    "V2WorkItemFactorModel",
    "V2SprintModel",
    "V2SprintScopeModel",
    "V2StatusVisitModel",
    "V2StatusVisitSampleModel",
    "V2SemanticCounterModel",
    "V2NaturalDecisionEvaluationModel",
)


def _first_import_statements() -> tuple[str, ...]:
    direct = (
        *(f"from app.v2.persistence.team_models import {name}" for name in TEAM_MODEL_NAMES),
        *(f"from app.v2.persistence.live_models import {name}" for name in LIVE_MODEL_NAMES),
        *(
            f"from app.v2.persistence.scrum_state_models import {name}"
            for name in SCRUM_MODEL_NAMES
        ),
        "from app.v2.persistence.unit_of_work import SqlAlchemyV2UnitOfWork",
        "from app.v2.persistence.scrum_state_mapper import SqlAlchemyScrumStateMapper",
    )
    lazy_names = (
        *LIVE_MODEL_NAMES,
        *SCRUM_MODEL_NAMES,
        "SemanticDeduplicationConflict",
        "SqlAlchemyV2UnitOfWork",
        "StaleRuntimeVersion",
        "V2UnitOfWork",
    )
    lazy = tuple(f"from app.v2.persistence import {name}" for name in lazy_names)
    return (*direct, *lazy, "from app.v2.persistence import SqlAlchemyScrumStateMapper")


class ProjectionAdapter(Protocol):
    calls: int

    def deliver(self, intent: ProjectionIntent) -> None: ...


class ExplodingProjectionAdapter:
    def __init__(self):
        self.calls = 0

    def deliver(self, intent: ProjectionIntent) -> None:
        self.calls += 1
        raise RuntimeError(f"external delivery failed for {intent.id}")


def _schema_creation_script(statement: str) -> str:
    return f"""
{statement}
from sqlalchemy import create_engine, event, inspect
from app.models import Base
required = {V2_TABLE_NAMES!r}
assert required <= set(Base.metadata.tables)
engine = create_engine('sqlite://')
@event.listens_for(engine, 'connect')
def enable_foreign_keys(connection, _record):
    connection.execute('PRAGMA foreign_keys=ON')
Base.metadata.create_all(engine)
assert required <= set(inspect(engine).get_table_names())
with engine.connect() as connection:
    assert connection.exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1
"""


def test_external_failure_after_commit_cannot_change_authoritative_state(
    v2_session_factory, resolved_blueprint_json, requested_at
):
    aggregate = create_aggregate(v2_session_factory, resolved_blueprint_json, requested_at)
    unit_of_work = SqlAlchemyV2UnitOfWork(v2_session_factory)
    adapter: ProjectionAdapter = ExplodingProjectionAdapter()
    committed = unit_of_work.commit_tick_slice(make_tick_commit(aggregate, 0, "adapter"))

    assert adapter.calls == 0
    with pytest.raises(RuntimeError, match="external delivery failed"):
        adapter.deliver(committed.projection_intents[0])

    activity = unit_of_work.page_activity(LedgerPageQuery(aggregate.team.id, None, None, 10))
    ground_truth = unit_of_work.page_ground_truth(
        LedgerPageQuery(aggregate.team.id, None, None, 10)
    )
    projection = unit_of_work.page_projection(
        ProjectionPageQuery(aggregate.team.id, None, None, 10)
    )
    assert unit_of_work.get_runtime(aggregate.team.id) == committed.runtime
    assert activity.items == committed.activity
    assert ground_truth.items == committed.ground_truth
    assert projection.items == committed.projection_intents
    assert all(item.status == "PENDING" for item in projection.items)


def test_unit_of_work_has_no_projection_adapter_or_external_client_boundary():
    module_path = Path(__file__).parents[3] / "app" / "v2" / "persistence" / "unit_of_work.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    delivered = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "deliver"
        for node in ast.walk(tree)
    )

    assert not any(name.startswith(("app.integrations", "app.engine")) for name in imported_modules)
    assert not any("jira" in name.lower() or "openai" in name.lower() for name in imported_modules)
    assert delivered is False


@pytest.mark.parametrize(
    "statement",
    _first_import_statements(),
)
def test_first_persistence_import_registers_all_v2_tables_and_creates_schema(statement):
    backend_root = Path(__file__).parents[3]

    result = subprocess.run(
        [sys.executable, "-B", "-c", _schema_creation_script(statement)],
        cwd=backend_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
