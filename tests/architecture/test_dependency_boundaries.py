"""Verify dependency boundary rules for current and future target layers.

For target layers that do NOT yet exist (core/, security/auth/, etc.), the
test verifies that the contract JSON defines the rule, and scans zero files.
The test does NOT skip — it runs and confirms the rule is in place even when
there are no files to check.
"""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "lingshu"


def _read_contract():
    raw = (ROOT / "docs" / "architecture" / "architecture-contract.json").read_text(
        encoding="utf-8"
    )
    return json.loads(raw)


def _collect_py_files(dir_path):
    """Return all .py files under dir_path, or empty list if dir doesn't exist."""
    if not dir_path.exists():
        return []
    return list(dir_path.rglob("*.py"))


def _extract_imports(file_path):
    """Extract all import targets from a Python file using AST."""
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


def _check_layer_boundary(layer_key, contract):
    """Check that a target layer has no forbidden imports."""
    layer_def = contract["target_layers"][layer_key]
    layer_path = ROOT / layer_def["path"]
    forbidden = layer_def["forbidden_import_prefixes"]

    py_files = _collect_py_files(layer_path)

    violations = []
    for py_file in py_files:
        imports = _extract_imports(py_file)
        for imp in imports:
            for prefix in forbidden:
                if imp == prefix or imp.startswith(prefix + "."):
                    violations.append(f"{py_file.relative_to(ROOT)}: imports {imp}")

    # Even if no files exist, the rule must be defined in the contract
    assert forbidden, f"Layer {layer_key} has no forbidden_import_prefixes defined"
    assert not violations, (
        f"Layer {layer_key} has forbidden import violations:\n"
        + "\n".join(violations)
    )


def test_core_layer_boundary():
    """core/ must not import Sanic, JWT, DB drivers, or any lingshu package."""
    contract = _read_contract()
    assert "core" in contract["target_layers"], "core layer rule not in contract"
    _check_layer_boundary("core", contract)


def test_security_auth_layer_boundary():
    """security/auth/ must not import Sanic, adapters, tenant, data, compat."""
    contract = _read_contract()
    assert "security_auth" in contract["target_layers"], "security_auth layer rule not in contract"
    _check_layer_boundary("security_auth", contract)


def test_contrib_tenant_layer_boundary():
    """contrib/tenant/ must not import Sanic, adapters, data, compat."""
    contract = _read_contract()
    assert "contrib_tenant" in contract["target_layers"], "contrib_tenant layer rule not in contract"
    _check_layer_boundary("contrib_tenant", contract)


def test_data_layer_boundary():
    """data/ must not import Sanic, request proxy, security, tenant, compat."""
    contract = _read_contract()
    assert "data" in contract["target_layers"], "data layer rule not in contract"
    _check_layer_boundary("data", contract)


def test_adapters_sanic_layer_boundary():
    """adapters/sanic/ must not import data, compat, or legacy middleware."""
    contract = _read_contract()
    assert "adapters_sanic" in contract["target_layers"], "adapters_sanic layer rule not in contract"
    _check_layer_boundary("adapters_sanic", contract)


def test_src_lingshu_does_not_import_project_code():
    """src/lingshu/** must not statically import app.* or config.*."""
    src_py_files = _collect_py_files(SRC)
    violations = []

    for py_file in src_py_files:
        imports = _extract_imports(py_file)
        for imp in imports:
            if imp.startswith("app.") or imp == "app":
                violations.append(f"{py_file.relative_to(ROOT)}: imports {imp}")
            if imp.startswith("config.") or imp == "config":
                # 'config' as a module name — but only flag if it looks like
                # the project config/ package, not stdlib or framework config
                rel = py_file.relative_to(SRC)
                # The framework has lingshu/config.py, not 'import config'
                # A bare 'import config' from src/lingshu would be unusual
                if str(rel) != "config.py":
                    violations.append(f"{py_file.relative_to(ROOT)}: imports {imp}")

    assert not violations, (
        "src/lingshu imports project code:\n" + "\n".join(violations)
    )
