import ast
from pathlib import Path


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
