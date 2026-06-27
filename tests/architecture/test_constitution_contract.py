"""Verify constitution, ADR, contract, and phase documents exist and are consistent."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _read_json(relative_path):
    return json.loads(_read(relative_path))


def test_development_constitution_exists():
    text = _read("docs/development/DEVELOPMENT_CONSTITUTION.md")
    assert "LingShu Development Constitution V1" in text
    assert "Roles And Permissions" in text
    assert "Sources Of Truth" in text
    assert "Phase Lifecycle" in text
    assert "Directory Ownership" in text
    assert "Dependency Direction" in text
    assert "Public API And Deprecation" in text
    assert "Testing And Verification" in text
    assert "ADR And Documentation" in text
    assert "Deviation Approval" in text
    assert "Violation Handling" in text
    assert "Constitution Version And Revision" in text


def test_agents_md_is_model_agnostic():
    text = _read("AGENTS.md")
    assert "Sources Of Truth" in text
    assert "docs/development/DEVELOPMENT_CONSTITUTION.md" in text
    assert "docs/development/CURRENT_PHASE.md" in text
    assert "Phase C1 Boundaries" not in text
    assert "Codex chat history" not in text.replace("Sources Of Truth", "")
    assert "The current work is phase C1 only" not in text
    assert "Do not start phases C2, C3, C4, C5, C6, D, E, or F" not in text


def test_agents_md_references_github_remote():
    text = _read("AGENTS.md")
    assert "`github`" in text
    assert "`main`" in text
    assert "fast-forward" in text.lower()


def test_current_phase_is_c2_rc():
    text = _read("docs/development/CURRENT_PHASE.md")
    assert "Current phase: C2-RC" in text
    assert "Current issue: #21" in text
    assert "Current writer: qwen" in text
    assert "qwen/phase-c2-rc-development-constitution" in text
    assert "Next phase allowed: no" in text
    assert "ed3ff04" in text


def test_handoff_doc_exists_and_is_model_agnostic():
    text = _read("docs/development/HANDOFF.md")
    assert "Branch:" in text
    assert "Worktree:" in text
    assert "Completed" in text
    assert "Remaining" in text
    assert "Phase C1" not in text
    assert "Third-Round" not in text


def test_task_template_exists():
    text = _read("docs/development/TASK_TEMPLATE.md")
    assert "Allowed Scope" in text
    assert "Prohibited Scope" in text
    assert "Test Contract" in text
    assert "Commit Rules" in text
    assert "Reporting Format" in text


def test_review_checklist_exists():
    text = _read("docs/development/REVIEW_CHECKLIST.md")
    assert "Scope" in text
    assert "Security" in text
    assert "API" in text
    assert "Dependencies" in text
    assert "Ownership" in text
    assert "Tests" in text
    assert "Merge Authority" in text


def test_all_adrs_exist():
    expected_adrs = [
        "docs/decisions/ADR-001-framework-project-ownership.md",
        "docs/decisions/ADR-002-public-api-and-deprecation.md",
        "docs/decisions/ADR-003-layer-dependency-direction.md",
        "docs/decisions/ADR-004-tenant-optional-capability.md",
        "docs/decisions/ADR-005-development-authority-and-merge-control.md",
    ]
    for adr_path in expected_adrs:
        text = _read(adr_path)
        assert "## Status" in text, f"{adr_path} missing Status"
        assert "## Context" in text, f"{adr_path} missing Context"
        assert "## Decision" in text, f"{adr_path} missing Decision"
        assert "## Consequences" in text, f"{adr_path} missing Consequences"
        assert "## Rejected Alternatives" in text, f"{adr_path} missing Rejected Alternatives"
        assert "## Change Conditions" in text, f"{adr_path} missing Change Conditions"


def test_architecture_contract_json_exists_and_valid():
    data = _read_json("docs/architecture/architecture-contract.json")

    required_top_keys = [
        "schema_version",
        "constitution_version",
        "status",
        "effective_on",
        "branch_prefixes",
        "research_branch_policy",
        "writer_handoff_policy",
        "ownership_roots",
        "stable_public_modules",
        "stable_public_symbols",
        "experimental_public_symbols",
        "legacy_api_candidates",
        "deprecated_api_candidates",
        "target_layers",
        "forbidden_import_prefixes",
        "project_forbidden_imports",
        "scaffold_forbidden_imports",
    ]
    for key in required_top_keys:
        assert key in data, f"architecture-contract.json missing key: {key}"

    roots = data["ownership_roots"]
    assert roots["framework"] == "src/lingshu"
    assert roots["project_app"] == "app"
    assert roots["project_config"] == "config"

    layers = data["target_layers"]
    expected_layers = ["core", "security_auth", "contrib_tenant", "data", "adapters_sanic", "compat"]
    for layer in expected_layers:
        assert layer in layers, f"target_layers missing: {layer}"
        layer_def = layers[layer]
        assert "path" in layer_def
        assert "forbidden_import_prefixes" in layer_def
        assert "allowed_lingshu_prefixes" in layer_def
        assert "allowed_third_party_prefixes" in layer_def


def test_old_codex_files_are_compatibility_pointers_only():
    current_phase = _read("docs/codex/CURRENT_PHASE.md")
    handoff = _read("docs/codex/HANDOFF.md")

    assert "docs/development/CURRENT_PHASE.md" in current_phase
    assert "docs/development/HANDOFF.md" in handoff
    assert "Current phase:" not in current_phase.replace("Compatibility Pointer", "")
    assert "Current issue:" not in current_phase
    assert "Updated at:" not in handoff.replace("Compatibility Pointer", "")


# --- Dynamic state separation tests (P0-1) ---

def test_stable_files_do_not_contain_current_writer():
    """Stable files must not hardcode current_writer or current_branch."""
    stable_files = [
        "AGENTS.md",
        "docs/development/DEVELOPMENT_CONSTITUTION.md",
        "docs/architecture/architecture-contract.json",
    ]
    for path in stable_files:
        text = _read(path)
        assert "current_writer" not in text.lower(), (
            f"{path} contains 'current_writer' — dynamic state must only be in CURRENT_PHASE/HANDOFF"
        )
        # The contract JSON should not have current_branch as a key
        if path.endswith(".json"):
            data = json.loads(text)
            assert "current_writer" not in data, (
                f"{path} has 'current_writer' key — must be removed"
            )
            assert "current_branch" not in data, (
                f"{path} has 'current_branch' key — must be removed"
            )


def test_current_phase_contains_writer_and_branch():
    """CURRENT_PHASE must contain the dynamic writer and branch state."""
    text = _read("docs/development/CURRENT_PHASE.md")
    assert "Current writer: qwen" in text
    assert "Current branch: qwen/phase-c2-rc-development-constitution" in text


def test_handoff_writer_matches_current_phase():
    """HANDOFF Writer must match CURRENT_PHASE Current writer."""
    handoff = _read("docs/development/HANDOFF.md")
    phase = _read("docs/development/CURRENT_PHASE.md")

    import re
    h_match = re.search(r"^Writer:\s*(.+)$", handoff, re.MULTILINE)
    p_match = re.search(r"^Current writer:\s*(.+)$", phase, re.MULTILINE)

    assert h_match, "HANDOFF missing 'Writer:' field"
    assert p_match, "CURRENT_PHASE missing 'Current writer:' field"

    assert h_match.group(1).strip() == p_match.group(1).strip(), (
        f"HANDOFF Writer '{h_match.group(1).strip()}' != "
        f"CURRENT_PHASE writer '{p_match.group(1).strip()}'"
    )


def test_handoff_branch_matches_current_phase():
    """HANDOFF Branch must match CURRENT_PHASE Current branch."""
    handoff = _read("docs/development/HANDOFF.md")
    phase = _read("docs/development/CURRENT_PHASE.md")

    import re
    h_match = re.search(r"^Branch:\s*(.+)$", handoff, re.MULTILINE)
    p_match = re.search(r"^Current branch:\s*(.+)$", phase, re.MULTILINE)

    assert h_match, "HANDOFF missing 'Branch:' field"
    assert p_match, "CURRENT_PHASE missing 'Current branch:' field"

    assert h_match.group(1).strip() == p_match.group(1).strip(), (
        f"HANDOFF Branch '{h_match.group(1).strip()}' != "
        f"CURRENT_PHASE branch '{p_match.group(1).strip()}'"
    )


def test_branch_prefix_matches_writer():
    """The current branch must start with the writer's registered prefix."""
    contract = _read_json("docs/architecture/architecture-contract.json")
    phase = _read("docs/development/CURRENT_PHASE.md")

    import re
    writer_match = re.search(r"^Current writer:\s*(.+)$", phase, re.MULTILINE)
    branch_match = re.search(r"^Current branch:\s*(.+)$", phase, re.MULTILINE)

    writer = writer_match.group(1).strip()
    branch = branch_match.group(1).strip()

    prefixes = contract["branch_prefixes"]
    assert writer in prefixes, f"Writer '{writer}' not in branch_prefixes registry"

    prefix = prefixes[writer]
    assert branch.startswith(prefix), (
        f"Branch '{branch}' does not start with prefix '{prefix}' for writer '{writer}'"
    )


# --- Governance status tests (P0-2) ---

def test_constitution_status_is_proposed():
    """Constitution must be Proposed until C2-RC PR is merged."""
    text = _read("docs/development/DEVELOPMENT_CONSTITUTION.md")
    assert "Proposed" in text
    assert "becomes Active when the C2-RC PR is merged" in text
    # Must NOT contain unconditional Active status
    lines = text.split("\n")
    for line in lines:
        if line.strip().startswith("Status:"):
            assert "Proposed" in line, f"Status line must say Proposed: {line}"
            break


def test_adrs_are_proposed_not_accepted():
    """All ADRs must be Proposed, not Accepted (until PR merge)."""
    adrs = [
        "docs/decisions/ADR-001-framework-project-ownership.md",
        "docs/decisions/ADR-002-public-api-and-deprecation.md",
        "docs/decisions/ADR-003-layer-dependency-direction.md",
        "docs/decisions/ADR-004-tenant-optional-capability.md",
        "docs/decisions/ADR-005-development-authority-and-merge-control.md",
    ]
    for adr_path in adrs:
        text = _read(adr_path)
        assert "Proposed" in text, f"{adr_path} must be Proposed"
        assert "accepted by merge of the C2-RC PR" in text


def test_architecture_docs_are_proposed_not_frozen():
    """Architecture rule docs must be Proposed, not Frozen."""
    arch_docs = [
        "docs/architecture/ownership-boundaries.md",
        "docs/architecture/dependency-rules.md",
        "docs/architecture/public-api-contract.md",
    ]
    for doc_path in arch_docs:
        text = _read(doc_path)
        assert "Proposed" in text, f"{doc_path} must be Proposed"
        assert "frozen by merge of the C2-RC PR" in text


def test_contract_status_is_proposed():
    """architecture-contract.json must have status=proposed."""
    data = _read_json("docs/architecture/architecture-contract.json")
    assert data.get("status") == "proposed"
    assert data.get("effective_on") == "c2-rc-pr-merge"


# --- Branch prefix registry tests ---

def test_all_developer_prefixes_are_unique():
    """Each developer in branch_prefixes must have a unique prefix."""
    contract = _read_json("docs/architecture/architecture-contract.json")
    prefixes = contract["branch_prefixes"]
    values = list(prefixes.values())
    assert len(values) == len(set(values))


def test_human_branch_requires_name():
    """The human prefix pattern must include a <name> placeholder."""
    contract = _read_json("docs/architecture/architecture-contract.json")
    prefixes = contract["branch_prefixes"]
    assert "human" in prefixes
    assert "<name>" in prefixes["human"]


# --- API tier integrity tests ---

_VALID_TIERS = {"Stable", "Experimental", "Internal", "Legacy", "Deprecated"}


def test_legacy_api_tiers_are_valid_enum():
    """Every legacy_api_candidates tier must be a standard enum value."""
    contract = _read_json("docs/architecture/architecture-contract.json")
    for entry in contract["legacy_api_candidates"]:
        tier = entry["tier"]
        assert tier in _VALID_TIERS, (
            f"Invalid tier '{tier}' for {entry['import_path']}. "
            f"Must be one of {_VALID_TIERS}"
        )


def test_legacy_facade_uses_kind_field():
    """Facade identity must use 'kind' field, not a custom tier value."""
    contract = _read_json("docs/architecture/architecture-contract.json")
    for entry in contract["legacy_api_candidates"]:
        if entry.get("kind") == "facade":
            assert entry["tier"] == "Legacy", (
                f"Facade {entry['import_path']} must be Legacy tier"
            )
        assert "Legacy facade" not in entry.get("tier", ""), (
            f"{entry['import_path']} uses invalid 'Legacy facade' tier — use kind:facade"
        )


def test_cache_facades_are_legacy():
    """Both cache facades must be classified as Legacy."""
    contract = _read_json("docs/architecture/architecture-contract.json")
    cache_entries = [
        e for e in contract["legacy_api_candidates"]
        if "cache" in e["import_path"]
    ]
    assert len(cache_entries) >= 2, (
        "Expected at least 2 cache facade entries (middleware.cache + extensions.cache)"
    )
    for entry in cache_entries:
        assert entry["tier"] == "Legacy", (
            f"{entry['import_path']} must be Legacy, got {entry['tier']}"
        )


def test_legacy_import_paths_exist():
    """Every legacy entry must pass the shared fail-closed validator."""
    contract = _read_json("docs/architecture/architecture-contract.json")
    for entry in contract["legacy_api_candidates"]:
        _validate_legacy_entry(entry)


def _validate_legacy_entry(entry: dict):
    """Shared fail-closed validator for a legacy_api_candidates entry.

    1. import_path must be importable (ImportError fails).
    2. Every symbol must exist (AttributeError fails).
    3. If kind == 'facade':
       - module must define __all__ (missing __all__ fails).
       - every contract symbol must be in __all__.
    """
    import importlib

    path = entry["import_path"]
    mod = importlib.import_module(path)
    for sym in entry["symbols"]:
        assert hasattr(mod, sym), (
            f"Legacy symbol '{sym}' not found in module '{path}'"
        )
    if entry.get("kind") == "facade":
        mod_all = getattr(mod, "__all__", None)
        assert mod_all is not None, (
            f"Facade module '{path}' must define __all__"
        )
        for sym in entry["symbols"]:
            assert sym in mod_all, (
                f"Facade symbol '{sym}' not in {path}.__all__"
            )


def test_nonexistent_legacy_import_fails(tmp_path):
    """Counter-example: a non-existent import_path must fail the validator."""
    fake_entry = {
        "import_path": "lingshu.nonexistent.fake_module_xyz",
        "symbols": ["FakeSymbol"],
        "tier": "Legacy",
    }
    try:
        _validate_legacy_entry(fake_entry)
    except ImportError:
        return
    raise AssertionError(
        "Validator should have raised ImportError for a non-existent module"
    )


def test_facade_without_all_fails(tmp_path, monkeypatch):
    """Counter-example: a facade entry whose module lacks __all__ must fail."""
    import sys
    import types

    fake_mod = types.ModuleType("lingshu._test_no_all_facade")
    fake_mod.FakeSymbol = object()
    # deliberately do NOT set __all__
    monkeypatch.setitem(sys.modules, "lingshu._test_no_all_facade", fake_mod)

    fake_entry = {
        "import_path": "lingshu._test_no_all_facade",
        "symbols": ["FakeSymbol"],
        "tier": "Legacy",
        "kind": "facade",
    }
    try:
        _validate_legacy_entry(fake_entry)
    except AssertionError as exc:
        assert "__all__" in str(exc), f"Wrong failure message: {exc}"
        return
    raise AssertionError(
        "Validator should have failed for facade without __all__"
    )


def test_facade_symbol_not_in_all_fails(tmp_path, monkeypatch):
    """Counter-example: a facade symbol not in __all__ must fail."""
    import sys
    import types

    fake_mod = types.ModuleType("lingshu._test_missing_all_entry")
    fake_mod.FakeSymbol = object()
    fake_mod.__all__ = ["OtherSymbol"]
    monkeypatch.setitem(sys.modules, "lingshu._test_missing_all_entry", fake_mod)

    fake_entry = {
        "import_path": "lingshu._test_missing_all_entry",
        "symbols": ["FakeSymbol"],
        "tier": "Legacy",
        "kind": "facade",
    }
    try:
        _validate_legacy_entry(fake_entry)
    except AssertionError as exc:
        assert "not in" in str(exc) and "__all__" in str(exc), (
            f"Wrong failure message: {exc}"
        )
        return
    raise AssertionError(
        "Validator should have failed for symbol not in __all__"
    )
