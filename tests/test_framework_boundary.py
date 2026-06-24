import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _imported_roots(node):
    if isinstance(node, ast.Import):
        return [alias.name.split(".", 1)[0] for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module:
        return [node.module.split(".", 1)[0]]
    return []


def test_framework_does_not_import_project_code():
    violations = []
    for path in sorted((ROOT / "framework").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            for root in _imported_roots(node):
                if root in {"app", "config"}:
                    violations.append(f"{path.relative_to(ROOT).as_posix()} imports {root}")

    assert violations == []
