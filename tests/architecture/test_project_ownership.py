"""Verify project ownership boundaries: app/ must not import lingshu.system."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_DIR = ROOT / "app"


def _collect_py_files(dir_path):
    if not dir_path.exists():
        return []
    return list(dir_path.rglob("*.py"))


def _extract_imports(file_path):
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    except SyntaxError:
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def test_app_code_does_not_import_lingshu_system():
    """app/** must not import lingshu.system.* — it is an internal package."""
    py_files = _collect_py_files(APP_DIR)
    violations = []

    for py_file in py_files:
        imports = _extract_imports(py_file)
        for imp in imports:
            if imp == "lingshu.system" or imp.startswith("lingshu.system."):
                violations.append(f"{py_file.relative_to(ROOT)}: imports {imp}")

    assert not violations, (
        "Project code imports lingshu.system (forbidden):\n"
        + "\n".join(violations)
    )


def test_app_language_exists():
    """app/language/ must exist for project-level overrides."""
    assert (APP_DIR / "language").exists()
    assert (APP_DIR / "language" / "zh-CN").exists()
    assert (APP_DIR / "language" / "en-US").exists()


def test_project_ownership_contract_in_json():
    """The architecture contract must define project_forbidden_imports."""
    import json

    raw = (ROOT / "docs" / "architecture" / "architecture-contract.json").read_text(
        encoding="utf-8"
    )
    contract = json.loads(raw)
    assert "lingshu.system" in contract["project_forbidden_imports"]
