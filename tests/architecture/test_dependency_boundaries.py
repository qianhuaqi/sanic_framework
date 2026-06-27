"""Verify dependency boundary rules for current and future target layers.

For target layers that do NOT yet exist (core/, security/auth/, etc.), the
test verifies that the contract JSON defines the rule, and scans zero files.
The test does NOT skip — it runs and confirms the rule is in place even when
there are no files to check.
"""

import json
from pathlib import Path

from tests.architecture.import_scan import extract_imports, collect_py_files

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "lingshu"


def _read_contract():
    raw = (ROOT / "docs" / "architecture" / "architecture-contract.json").read_text(
        encoding="utf-8"
    )
    return json.loads(raw)


_STDLIB_TOP_LEVEL = frozenset({
    "abc", "argparse", "ast", "asyncio", "base64", "bisect",
    "calendar", "collections", "concurrent", "configparser",
    "contextlib", "copy", "csv", "datetime", "decimal", "difflib",
    "enum", "errno", "faulthandler", "fcntl", "fnmatch", "functools",
    "gc", "getopt", "getpass", "glob", "hashlib", "heapq", "hmac",
    "html", "http", "importlib", "inspect", "io", "ipaddress",
    "itertools", "json", "logging", "math", "mimetypes", "multiprocessing",
    "operator", "os", "pathlib", "pickle", "platform", "pprint",
    "queue", "random", "re", "shlex", "shutil", "signal", "socket",
    "sqlite3", "ssl", "statistics", "string", "struct", "subprocess",
    "sys", "tempfile", "textwrap", "threading", "time", "traceback",
    "typing", "unittest", "urllib", "uuid", "warnings", "weakref",
    "xml", "zipfile", "zlib", "__future__",
})


def _is_stdlib_import(imp: str) -> bool:
    top = imp.split(".")[0]
    return top in _STDLIB_TOP_LEVEL


def _check_layer_allowlist(layer_key: str, contract):
    """Check that a target layer only imports allowed dependencies (allowlist)."""
    layer_def = contract["target_layers"][layer_key]
    layer_path = ROOT / layer_def["path"]
    allowed_lingshu = layer_def.get("allowed_lingshu_prefixes", [])
    allowed_third = layer_def.get("allowed_third_party_prefixes", [])
    forbidden = layer_def["forbidden_import_prefixes"]

    py_files = collect_py_files(layer_path)

    violations = []
    for py_file in py_files:
        imports = extract_imports(py_file)
        for imp in imports:
            for prefix in forbidden:
                if imp == prefix or imp.startswith(prefix + "."):
                    violations.append(f"{py_file.relative_to(ROOT)}: forbidden import '{imp}'")

            if imp.startswith("lingshu.") or imp == "lingshu":
                allowed = False
                for prefix in allowed_lingshu:
                    if imp == prefix or imp.startswith(prefix + "."):
                        allowed = True
                        break
                if not allowed:
                    violations.append(
                        f"{py_file.relative_to(ROOT)}: lingshu import '{imp}' "
                        f"not in allowed_lingshu_prefixes {allowed_lingshu}"
                    )
            elif not _is_stdlib_import(imp):
                allowed = False
                for prefix in allowed_third:
                    if imp == prefix or imp.startswith(prefix + "."):
                        allowed = True
                        break
                if not allowed:
                    violations.append(
                        f"{py_file.relative_to(ROOT)}: third-party import '{imp}' "
                        f"not in allowed_third_party_prefixes {allowed_third}"
                    )

    assert forbidden, f"Layer {layer_key} has no forbidden_import_prefixes defined"
    assert not violations, (
        f"Layer {layer_key} has import violations:\n" + "\n".join(violations)
    )


def _check_layer_boundary(layer_key, contract):
    """Check that a target layer has no forbidden imports (blacklist)."""
    layer_def = contract["target_layers"][layer_key]
    layer_path = ROOT / layer_def["path"]
    forbidden = layer_def["forbidden_import_prefixes"]

    py_files = collect_py_files(layer_path)

    violations = []
    for py_file in py_files:
        imports = extract_imports(py_file)
        for imp in imports:
            for prefix in forbidden:
                if imp == prefix or imp.startswith(prefix + "."):
                    violations.append(f"{py_file.relative_to(ROOT)}: imports {imp}")

    assert forbidden, f"Layer {layer_key} has no forbidden_import_prefixes defined"
    assert not violations, (
        f"Layer {layer_key} has forbidden import violations:\n"
        + "\n".join(violations)
    )


def test_core_layer_boundary():
    """core/ must not import Sanic, JWT, DB drivers, or any lingshu package."""
    contract = _read_contract()
    assert "core" in contract["target_layers"]
    _check_layer_boundary("core", contract)


def test_core_layer_allowlist():
    """core/ allowlist: only stdlib. Any lingshu.* or third-party rejected."""
    contract = _read_contract()
    _check_layer_allowlist("core", contract)


def test_security_auth_layer_boundary():
    """security/auth/ must not import Sanic, adapters, tenant, data, compat."""
    contract = _read_contract()
    assert "security_auth" in contract["target_layers"]
    _check_layer_boundary("security_auth", contract)


def test_security_auth_layer_allowlist():
    """security/auth/ allowlist: lingshu.core + jwt only."""
    contract = _read_contract()
    _check_layer_allowlist("security_auth", contract)


def test_contrib_tenant_layer_boundary():
    """contrib/tenant/ must not import Sanic, adapters, data, compat."""
    contract = _read_contract()
    assert "contrib_tenant" in contract["target_layers"]
    _check_layer_boundary("contrib_tenant", contract)


def test_contrib_tenant_layer_allowlist():
    """contrib/tenant/ allowlist: lingshu.core + lingshu.security.auth only."""
    contract = _read_contract()
    _check_layer_allowlist("contrib_tenant", contract)


def test_data_layer_boundary():
    """data/ must not import Sanic, request proxy, security, tenant, compat."""
    contract = _read_contract()
    assert "data" in contract["target_layers"]
    _check_layer_boundary("data", contract)


def test_data_layer_allowlist():
    """data/ allowlist: lingshu.core + approved DB drivers only."""
    contract = _read_contract()
    _check_layer_allowlist("data", contract)


def test_adapters_sanic_layer_boundary():
    """adapters/sanic/ must not import data, compat, or legacy middleware."""
    contract = _read_contract()
    assert "adapters_sanic" in contract["target_layers"]
    _check_layer_boundary("adapters_sanic", contract)


def test_adapters_sanic_layer_allowlist():
    """adapters/sanic/ allowlist: core + security.auth + contrib.tenant + sanic."""
    contract = _read_contract()
    _check_layer_allowlist("adapters_sanic", contract)


def test_src_lingshu_does_not_import_project_code():
    """src/lingshu/** must not statically import app.* or config.*."""
    src_py_files = collect_py_files(SRC)
    violations = []

    for py_file in src_py_files:
        imports = extract_imports(py_file)
        for imp in imports:
            if imp.startswith("app.") or imp == "app":
                violations.append(f"{py_file.relative_to(ROOT)}: imports {imp}")
            if imp.startswith("config.") or imp == "config":
                rel = py_file.relative_to(SRC)
                if str(rel) != "config.py":
                    violations.append(f"{py_file.relative_to(ROOT)}: imports {imp}")

    assert not violations, (
        "src/lingshu imports project code:\n" + "\n".join(violations)
    )


def test_extract_imports_catches_from_lingshu_import_system(tmp_path):
    """The AST must resolve 'from lingshu import system' to 'lingshu.system'."""
    test_file = tmp_path / "test_module.py"
    test_file.write_text("from lingshu import system\n", encoding="utf-8")
    imports = extract_imports(test_file)
    assert "lingshu.system" in imports


def test_extract_imports_catches_from_lingshu_import_middleware(tmp_path):
    """The AST must resolve 'from lingshu import middleware' to 'lingshu.middleware'."""
    test_file = tmp_path / "test_module.py"
    test_file.write_text("from lingshu import middleware\n", encoding="utf-8")
    imports = extract_imports(test_file)
    assert "lingshu.middleware" in imports


def test_extract_imports_fails_closed_on_syntax_error(tmp_path):
    """SyntaxError must propagate, NOT return an empty list."""
    test_file = tmp_path / "broken.py"
    test_file.write_text("def broken(:\n", encoding="utf-8")
    try:
        extract_imports(test_file)
    except SyntaxError:
        return
    raise AssertionError("SyntaxError should have been raised")


def test_extract_imports_resolves_relative_import(tmp_path):
    """Relative imports must be resolved to absolute lingshu.* paths."""
    pkg_dir = tmp_path / "src" / "lingshu" / "security" / "auth"
    pkg_dir.mkdir(parents=True)
    test_file = pkg_dir / "base.py"
    test_file.write_text("from ...core import types\n", encoding="utf-8")

    imports = extract_imports(test_file, repo_root=tmp_path)
    assert any("lingshu.core" in imp for imp in imports), (
        f"Expected 'lingshu.core' in resolved relative imports, got: {imports}"
    )


def test_core_forbids_lingshu_exception():
    """core/ must forbid importing lingshu.exception (counter-example test)."""
    contract = _read_contract()
    forbidden = contract["target_layers"]["core"]["forbidden_import_prefixes"]
    assert "lingshu.exception" in forbidden


def test_contract_target_layers_have_allowlist_fields():
    """Every target layer must define allowlist fields (not just blacklist)."""
    contract = _read_contract()
    for layer_key, layer_def in contract["target_layers"].items():
        assert "allowed_stdlib" in layer_def, f"{layer_key} missing allowed_stdlib"
        assert "allowed_lingshu_prefixes" in layer_def, f"{layer_key} missing allowed_lingshu_prefixes"
        assert "allowed_third_party_prefixes" in layer_def, f"{layer_key} missing allowed_third_party_prefixes"
