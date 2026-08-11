import ast
import importlib
import inspect
from pathlib import Path
from typing import get_type_hints

from app.v2.persistence.unit_of_work import SqlAlchemyV2UnitOfWork, V2UnitOfWork


def test_v2_imports_only_allowed_legacy_boundaries():
    v2_root = Path(__file__).parents[3] / "app" / "v2"
    prohibited_prefixes = ("app.engine", "app.integrations")
    prohibited_symbols = {"PrecomputationRun", "ScheduledEvent", "JiraWriteQueueEntry"}

    for source_path in v2_root.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(prohibited_prefixes)
                if node.module.startswith("app.models"):
                    assert node.module == "app.models.base"
                    assert all(alias.name == "Base" for alias in node.names)
            if isinstance(node, ast.Name):
                assert node.id not in prohibited_symbols


def test_public_unit_of_work_constructor_declares_none_return_type():
    signature = inspect.signature(SqlAlchemyV2UnitOfWork.__init__)

    assert signature.return_annotation is None


def test_live_slice_digest_reuses_shared_canonical_helper():
    source_path = Path(__file__).parents[3] / "app" / "v2" / "domain" / "live_slice.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    helper_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "canonical_sha256"
    ]

    assert "hashlib" not in imported_names
    assert "canonical_sha256" in imported_names
    assert helper_calls


def _task3_source_trees() -> tuple[ast.Module, ...]:
    domain_root = Path(__file__).parents[3] / "app" / "v2" / "domain"
    return tuple(
        ast.parse((domain_root / filename).read_text(encoding="utf-8"))
        for filename in ("deterministic_rng.py", "immutable_value.py", "sampling.py")
    )


def test_task3_modules_import_only_pure_domain_dependencies():
    prohibited_prefixes = (
        "app.database",
        "app.engine",
        "app.integrations",
        "app.models",
        "app.v2.persistence",
        "random",
        "sqlalchemy",
    )

    for tree in _task3_source_trees():
        imports = (
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        assert all(not name.startswith(prohibited_prefixes) for name in imports)
        imported_modules = (
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert all(not name.startswith(prohibited_prefixes) for name in imported_modules)


def test_task3_modules_have_no_hidden_nondeterminism_or_clock_sources():
    prohibited_calls = {"hash", "uuid4", "now", "utcnow", "time"}

    for tree in _task3_source_trees():
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        called_attributes = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert not prohibited_calls & (called_names | called_attributes)


def test_task3_modules_have_no_mutable_module_level_state():
    mutable_nodes = (ast.Dict, ast.List, ast.Set)

    for tree in _task3_source_trees():
        assignments = (node for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign)))
        for assignment in assignments:
            assert not isinstance(assignment.value, mutable_nodes)


def test_task3_public_exports_are_additive_and_closed():
    domain = importlib.import_module("app.v2.domain")
    expected = {
        "CreationKind",
        "DecisionOccurrence",
        "DecisionType",
        "DeterministicRandomStream",
        "DwellAnchors",
        "DurationSample",
        "TouchBounds",
        "UniformDraw",
        "dependency_rng_id",
        "dwell_anchors",
        "item_rng_id",
        "member_rng_id",
        "rework_rng_id",
        "run_rng_id",
        "sample_dwell",
        "sample_touch",
        "sprint_rng_id",
        "team_rng_id",
        "touch_bounds",
        "visit_rng_id",
    }

    assert expected <= set(domain.__all__)
    assert all(hasattr(domain, name) for name in expected)


def _task4_source_trees() -> tuple[ast.Module, ...]:
    domain_root = Path(__file__).parents[3] / "app" / "v2" / "domain"
    return tuple(
        ast.parse((domain_root / filename).read_text(encoding="utf-8"))
        for filename in (
            "business_calendar.py",
            "iana_timezone.py",
            "us_federal_calendar.py",
        )
    )


def test_task4_modules_import_only_pure_local_domain_dependencies():
    prohibited_prefixes = (
        "aiohttp",
        "app.database",
        "app.engine",
        "app.integrations",
        "app.models",
        "app.v2.persistence",
        "httpx",
        "requests",
        "socket",
        "sqlalchemy",
        "urllib",
    )

    for tree in _task4_source_trees():
        imported = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        ]
        imported.extend(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert all(not name.startswith(prohibited_prefixes) for name in imported)


def test_task4_modules_do_not_read_host_clock_locale_or_timezone():
    prohibited_calls = {"now", "today", "utcnow"}

    for tree in _task4_source_trees():
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        called_attributes = {
            node.func.attr for node in calls if isinstance(node.func, ast.Attribute)
        }
        assert not prohibited_calls & called_attributes
        local_timezone_calls = [
            node
            for node in calls
            if isinstance(node.func, ast.Attribute)
            and node.func.attr == "astimezone"
            and not node.args
            and not node.keywords
        ]
        assert not local_timezone_calls


def test_task4_modules_have_no_mutable_module_level_state():
    mutable_nodes = (ast.Dict, ast.List, ast.Set)

    for tree in _task4_source_trees():
        assignments = (node for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign)))
        for assignment in assignments:
            assert not isinstance(assignment.value, mutable_nodes)


def test_task4_public_exports_are_additive_and_closed():
    domain = importlib.import_module("app.v2.domain")
    expected = {
        "BusinessCalendar",
        "BusinessTimeAddition",
        "CadenceRule",
        "DualElapsed",
        "HolidayHorizon",
        "UtcInterval",
        "cadence_boundary",
        "extend_us_federal_horizon",
        "materialize_us_federal_horizon",
    }

    assert expected <= set(domain.__all__)
    assert all(hasattr(domain, name) for name in expected)


def test_task5_domain_is_pure_and_has_no_hidden_allocation_or_clock():
    source_path = Path(__file__).parents[3] / "app" / "v2" / "domain" / "scrum_state.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    prohibited_imports = (
        "app.database",
        "app.engine",
        "app.integrations",
        "app.models",
        "app.v2.persistence",
        "random",
        "sqlalchemy",
    )
    imports = _imported_modules(tree)
    assert all(not name.startswith(prohibited_imports) for name in imports)
    called = _called_attributes(tree)
    assert not {"now", "today", "utcnow", "commit", "flush"} & called
    public_functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    assert not {"allocate", "advance", "transition", "claim"} & public_functions


def _imported_modules(tree: ast.Module) -> list[str]:
    imported = [
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    ]
    imported.extend(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    return imported


def _called_attributes(tree: ast.Module) -> set[str]:
    return {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


def test_task5_mapper_has_caller_owned_transaction_boundary():
    source_path = Path(__file__).parents[3] / "app" / "v2" / "persistence" / "scrum_state_mapper.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "flush" in called
    assert not {"begin", "commit", "rollback", "close"} & called
    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.startswith(("app.engine", "app.integrations"))
        for node in ast.walk(tree)
    )


def test_task5_relational_state_contains_no_blueprint_configuration_columns():
    models = importlib.import_module("app.v2.persistence.scrum_state_models")
    prohibited = {
        "name",
        "role",
        "responsibility",
        "proficiency",
        "wip",
        "route",
        "timing_grid",
        "calendar",
        "policy",
        "nominal_capacity",
    }
    for model_name in _task5_persistence_exports() - {"SqlAlchemyScrumStateMapper"}:
        column_names = {column.name for column in getattr(models, model_name).__table__.columns}
        assert not any(token in name for name in column_names for token in prohibited)


def test_task5_public_exports_are_additive_and_closed():
    domain = importlib.import_module("app.v2.domain")
    persistence = importlib.import_module("app.v2.persistence")
    domain_exports = _task5_domain_exports()
    persistence_exports = _task5_persistence_exports()
    assert domain_exports <= set(domain.__all__)
    assert persistence_exports <= set(persistence.__all__)
    assert all(hasattr(domain, name) for name in domain_exports)
    assert all(hasattr(persistence, name) for name in persistence_exports)


def _task5_domain_exports() -> set[str]:
    return {
        "FactorKind",
        "MemberAvailabilityOverlay",
        "MemberBusinessDateConsumption",
        "MemberIdentity",
        "NaturalDecisionEvaluation",
        "ScrumStateQuery",
        "ScrumStateSnapshot",
        "ScrumStateWriteSet",
        "SemanticCounter",
        "SemanticCounterKind",
        "SemanticCounterScope",
        "SimulatorRank",
        "SprintLifecycle",
        "SprintScopeEntry",
        "SprintState",
        "StatusVisitLifecycle",
        "StatusVisitSample",
        "StatusVisitSampleInput",
        "StatusVisitState",
        "WorkItemFactor",
        "WorkItemLifecycle",
        "WorkItemState",
        "WorkPriority",
    }


def _task5_persistence_exports() -> set[str]:
    return {
        "SqlAlchemyScrumStateMapper",
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
    }


def _task6_source_tree(filename: str) -> ast.Module:
    v2_root = Path(__file__).parents[3] / "app" / "v2"
    return ast.parse((v2_root / filename).read_text(encoding="utf-8"))


def _called_names(tree: ast.Module) -> set[str]:
    names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    return names | _called_attributes(tree)


TASK6_EXTERNAL_IMPORTS = (
    "aiohttp",
    "app.engine",
    "app.integrations",
    "boto3",
    "httpx",
    "openai",
    "random",
    "requests",
    "secrets",
    "socket",
    "time",
    "urllib",
)
TASK6_HIDDEN_RUNTIME_CALLS = frozenset(
    {
        "DeterministicRandomStream",
        "deliver",
        "now",
        "random",
        "sample_dwell",
        "sample_touch",
        "time",
        "today",
        "utcnow",
        "uuid4",
    }
)
TASK6_FORBIDDEN_RUNTIME_SYMBOLS = frozenset(
    {
        "DeterministicRandomStream",
        "UniformDraw",
        "cadence_boundary",
        "sample_dwell",
        "sample_touch",
    }
)
TASK6_HIDDEN_OPERATION_PREFIXES = (
    "allocate",
    "recalculate",
    "resample",
    "schedule",
    "synthesize",
    "transition",
)


def _assert_no_task6_external_or_hidden_runtime(
    tree: ast.Module, extra_imports: tuple[str, ...] = ()
) -> None:
    imports = (*TASK6_EXTERNAL_IMPORTS, *extra_imports)
    assert all(not name.startswith(imports) for name in _imported_modules(tree))
    imported_symbols = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not TASK6_FORBIDDEN_RUNTIME_SYMBOLS & imported_symbols
    assert not any("jira" in name.lower() or "openai" in name.lower() for name in imported_symbols)
    called = _called_names(tree)
    assert not TASK6_HIDDEN_RUNTIME_CALLS & called
    hidden_operations = {
        name
        for name in called
        if name.lstrip("_").startswith(TASK6_HIDDEN_OPERATION_PREFIXES)
    }
    assert not hidden_operations


def test_task6_authoritative_domain_has_no_external_or_hidden_runtime_behavior():
    tree = _task6_source_tree("domain/authoritative_slice.py")
    extra_imports = (
        "app.database",
        "app.models",
        "app.v2.application",
        "app.v2.persistence",
        "sqlalchemy",
    )

    _assert_no_task6_external_or_hidden_runtime(tree, extra_imports)


def test_task6_unit_of_work_exposes_exact_authoritative_operation():
    domain = importlib.import_module("app.v2.domain.authoritative_slice")
    expected_hints = {
        "commit": domain.AuthoritativeTickSliceCommit,
        "return": domain.CommittedAuthoritativeTickSlice,
    }
    operations = (
        V2UnitOfWork.commit_authoritative_slice,
        SqlAlchemyV2UnitOfWork.commit_authoritative_slice,
    )

    for operation in operations:
        assert tuple(inspect.signature(operation).parameters) == ("self", "commit")
        assert get_type_hints(operation) == expected_hints
    assert getattr(V2UnitOfWork.commit_authoritative_slice, "__isabstractmethod__", False)


def test_task6_public_exports_are_additive_and_importable():
    domain = importlib.import_module("app.v2.domain")
    persistence = importlib.import_module("app.v2.persistence")
    domain_exports = {
        "AuthoritativeTickSliceCommit",
        "CommittedAuthoritativeTickSlice",
        "EligibleNaturalDecisionClaim",
        "SemanticCounterClaim",
    }
    persistence_exports = {"NaturalEligibilityConflict", "StaleSemanticCounter"}

    assert domain_exports <= set(domain.__all__)
    assert persistence_exports <= set(persistence.__all__)
    assert all(hasattr(domain, name) for name in domain_exports)
    assert all(hasattr(persistence, name) for name in persistence_exports)


def test_task6_unit_of_work_imports_no_external_clients_or_hidden_clock():
    tree = _task6_source_tree("persistence/unit_of_work.py")

    _assert_no_task6_external_or_hidden_runtime(tree)


def test_authoritative_operation_never_delegates_to_the_public_live_slice_operation():
    tree = _task6_source_tree("persistence/unit_of_work.py")
    concrete = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SqlAlchemyV2UnitOfWork"
    )
    method = next(
        node
        for node in concrete.body
        if isinstance(node, ast.FunctionDef) and node.name == "commit_authoritative_slice"
    )
    called = {
        node.func.attr
        for node in ast.walk(method)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert "commit_tick_slice" not in called


def test_task6_creates_no_alembic_revision_016():
    versions = Path(__file__).parents[3] / "alembic" / "versions"
    revisions = {
        node.value.value
        for path in versions.glob("*.py")
        for node in ast.parse(path.read_text(encoding="utf-8")).body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "revision"
        and isinstance(node.value, ast.Constant)
    }

    assert "015" in revisions
    assert "016" not in revisions
    assert not tuple(versions.glob("016*.py"))
