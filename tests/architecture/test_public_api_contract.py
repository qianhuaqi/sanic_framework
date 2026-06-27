"""Verify that Stable public API modules and symbols are importable and consistent."""

import importlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read_contract():
    raw = (ROOT / "docs" / "architecture" / "architecture-contract.json").read_text(
        encoding="utf-8"
    )
    return json.loads(raw)


def test_stable_public_modules_exist():
    """Every module listed as stable_public_modules must be importable."""
    contract = _read_contract()
    for module_name in contract["stable_public_modules"]:
        mod = importlib.import_module(module_name)
        assert mod is not None, f"Cannot import stable module: {module_name}"


def test_stable_public_symbols_are_importable():
    """Every symbol listed as stable must be importable from its module."""
    contract = _read_contract()
    for module_name, symbols in contract["stable_public_symbols"].items():
        mod = importlib.import_module(module_name)
        for symbol_name in symbols:
            assert hasattr(mod, symbol_name), (
                f"Stable symbol '{symbol_name}' not found in module '{module_name}'"
            )


def test_stable_symbols_match_all_exports():
    """The contract's stable symbols must match the actual __all__ exports."""
    contract = _read_contract()

    for module_name, expected_symbols in contract["stable_public_symbols"].items():
        mod = importlib.import_module(module_name)
        actual_all = getattr(mod, "__all__", None)
        if actual_all is not None:
            actual_set = set(actual_all)
            expected_set = set(expected_symbols)
            # Every symbol in the contract must be in __all__
            missing_from_all = expected_set - actual_set
            assert not missing_from_all, (
                f"Contract lists symbols not in {module_name}.__all__: {missing_from_all}"
            )


def test_lingshu_auth_does_not_export_auth_or_token_required():
    """The new auth facade must NOT export legacy Auth or token_required."""
    import lingshu.auth as auth_mod

    assert not hasattr(auth_mod, "Auth"), (
        "lingshu.auth must not export 'Auth' — it is a legacy symbol"
    )
    assert not hasattr(auth_mod, "token_required"), (
        "lingshu.auth must not export 'token_required' — it is a legacy symbol"
    )


def test_stable_facade_not_accidentally_removed():
    """Top-level facade modules must not be deleted."""
    required_modules = [
        "lingshu",
        "lingshu.auth",
        "lingshu.tenant",
        "lingshu.router",
        "lingshu.model",
    ]
    for module_name in required_modules:
        mod = importlib.import_module(module_name)
        assert mod is not None
