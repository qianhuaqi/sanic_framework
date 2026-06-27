"""Verify project ownership boundaries: app/ and config/ must not import lingshu.system."""

import json
from pathlib import Path

from tests.architecture.import_scan import extract_imports, collect_py_files

ROOT = Path(__file__).resolve().parents[2]
APP_DIR = ROOT / "app"
CONFIG_DIR = ROOT / "config"


def _read_contract():
    raw = (ROOT / "docs" / "architecture" / "architecture-contract.json").read_text(
        encoding="utf-8"
    )
    return json.loads(raw)


def test_app_code_does_not_import_lingshu_system():
    """app/** must not import lingshu.system.* — it is an internal package."""
    py_files = collect_py_files(APP_DIR)
    violations = []

    for py_file in py_files:
        imports = extract_imports(py_file)
        for imp in imports:
            if imp == "lingshu.system" or imp.startswith("lingshu.system."):
                violations.append(f"{py_file.relative_to(ROOT)}: imports {imp}")

    assert not violations, (
        "Project code imports lingshu.system (forbidden):\n"
        + "\n".join(violations)
    )


def test_config_code_does_not_import_lingshu_system():
    """config/** must not import lingshu.system.* — it is an internal package."""
    py_files = collect_py_files(CONFIG_DIR)
    violations = []

    for py_file in py_files:
        imports = extract_imports(py_file)
        for imp in imports:
            if imp == "lingshu.system" or imp.startswith("lingshu.system."):
                violations.append(f"{py_file.relative_to(ROOT)}: imports {imp}")

    assert not violations, (
        "Config code imports lingshu.system (forbidden):\n"
        + "\n".join(violations)
    )


def test_app_language_exists():
    """app/language/ must exist for project-level overrides."""
    assert (APP_DIR / "language").exists()
    assert (APP_DIR / "language" / "zh-CN").exists()
    assert (APP_DIR / "language" / "en-US").exists()


def test_project_ownership_contract_in_json():
    """The architecture contract must define project_forbidden_imports."""
    contract = _read_contract()
    assert "lingshu.system" in contract["project_forbidden_imports"]
