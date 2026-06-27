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


def _build_symbol_tier_map(contract):
    """Build {module: {symbol: tier}} from stable and experimental contracts."""
    tier_map = {}
    for module_name, symbols in contract.get("stable_public_symbols", {}).items():
        tier_map.setdefault(module_name, {})
        for sym in symbols:
            tier_map[module_name][sym] = "Stable"
    for module_name, symbols in contract.get("experimental_public_symbols", {}).items():
        tier_map.setdefault(module_name, {})
        for sym in symbols:
            tier_map[module_name][sym] = "Experimental"
    return tier_map


def test_all_all_symbols_are_classified():
    """Every symbol in each module's __all__ must be in Stable or Experimental."""
    contract = _read_contract()
    tier_map = _build_symbol_tier_map(contract)

    all_classified_modules = set(contract["stable_public_symbols"].keys()) | set(
        contract.get("experimental_public_symbols", {}).keys()
    )

    unclassified = []
    for module_name in all_classified_modules:
        mod = importlib.import_module(module_name)
        actual_all = getattr(mod, "__all__", None)
        if actual_all is None:
            continue
        classified = tier_map.get(module_name, {})
        for sym in actual_all:
            if sym not in classified:
                unclassified.append(f"{module_name}.{sym}")

    assert not unclassified, (
        "Symbols in __all__ but not classified in any tier: "
        + ", ".join(unclassified)
    )


def test_no_symbol_in_both_stable_and_experimental():
    """No symbol may appear in both Stable and Experimental tiers."""
    contract = _read_contract()
    stable = contract.get("stable_public_symbols", {})
    experimental = contract.get("experimental_public_symbols", {})

    for module_name in set(stable.keys()) & set(experimental.keys()):
        overlap = set(stable[module_name]) & set(experimental[module_name])
        assert not overlap, (
            f"Module {module_name} has symbols in both Stable and Experimental: {overlap}"
        )


def test_no_unclassified_public_symbols_exist():
    """No public symbol should exist outside Stable or Experimental tiers.

    This verifies the union of Stable + Experimental equals the full __all__
    for every classified module.
    """
    contract = _read_contract()
    tier_map = _build_symbol_tier_map(contract)

    all_classified_modules = set(contract["stable_public_symbols"].keys()) | set(
        contract.get("experimental_public_symbols", {}).keys()
    )

    for module_name in all_classified_modules:
        mod = importlib.import_module(module_name)
        actual_all = getattr(mod, "__all__", None)
        if actual_all is None:
            continue
        classified = set(tier_map.get(module_name, {}).keys())
        actual_set = set(actual_all)
        extra_in_contract = classified - actual_set
        assert not extra_in_contract, (
            f"Contract lists symbols not in {module_name}.__all__: {extra_in_contract}"
        )


def test_experimental_symbols_are_importable():
    """Every symbol listed as experimental must be importable from its module."""
    contract = _read_contract()
    assert "experimental_public_symbols" in contract, (
        "architecture-contract.json missing experimental_public_symbols key"
    )
    for module_name, symbols in contract["experimental_public_symbols"].items():
        mod = importlib.import_module(module_name)
        for symbol_name in symbols:
            assert hasattr(mod, symbol_name), (
                f"Experimental symbol '{symbol_name}' not found in module '{module_name}'"
            )
