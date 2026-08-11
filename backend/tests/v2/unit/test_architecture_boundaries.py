import ast
import inspect
from pathlib import Path

from app.v2.persistence.unit_of_work import SqlAlchemyV2UnitOfWork


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
