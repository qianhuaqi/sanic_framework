"""Verify constitution, ADR, contract, and phase documents exist and are consistent."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


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
    # Must not be hard-coded to a single model
    assert "Codex chat history" not in text.replace("Sources Of Truth", "")
    # The old C1-specific text must be gone
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
    assert "qwen/phase-c2-rc-development-constitution" in text
    assert "Next phase allowed: no" in text
    assert "ed3ff04" in text  # PR #20 merge commit


def test_handoff_doc_exists_and_is_model_agnostic():
    text = _read("docs/development/HANDOFF.md")
    assert "Branch:" in text
    assert "Worktree:" in text
    assert "Completed" in text
    assert "Remaining" in text
    # Must not contain stale C1 content
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
    raw = _read("docs/architecture/architecture-contract.json")
    data = json.loads(raw)

    required_top_keys = [
        "schema_version",
        "constitution_version",
        "branch_prefixes",
        "current_writer",
        "current_branch",
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

    # ownership_roots must have framework and project entries
    roots = data["ownership_roots"]
    assert roots["framework"] == "src/lingshu"
    assert roots["project_app"] == "app"
    assert roots["project_config"] == "config"

    # target_layers must define all expected future layers
    layers = data["target_layers"]
    expected_layers = ["core", "security_auth", "contrib_tenant", "data", "adapters_sanic", "compat"]
    for layer in expected_layers:
        assert layer in layers, f"target_layers missing: {layer}"
        layer_def = layers[layer]
        assert "path" in layer_def, f"{layer} missing 'path'"
        assert "forbidden_import_prefixes" in layer_def, f"{layer} missing 'forbidden_import_prefixes'"


def test_old_codex_files_are_compatibility_pointers_only():
    current_phase = _read("docs/codex/CURRENT_PHASE.md")
    handoff = _read("docs/codex/HANDOFF.md")

    # Must point to the new location
    assert "docs/development/CURRENT_PHASE.md" in current_phase
    assert "docs/development/HANDOFF.md" in handoff

    # Must NOT contain duplicate phase facts
    assert "Current phase:" not in current_phase.replace("Compatibility Pointer", "")
    assert "Current issue:" not in current_phase
    assert "Updated at:" not in handoff.replace("Compatibility Pointer", "")


def _read_json(relative_path):
    return json.loads(_read(relative_path))


def test_branch_prefix_matches_current_writer():
    """current_branch must start with the prefix for current_writer."""
    contract = _read_json("docs/architecture/architecture-contract.json")
    writer = contract["current_writer"]
    branch = contract["current_branch"]
    prefixes = contract["branch_prefixes"]

    assert writer in prefixes, f"current_writer '{writer}' not in branch_prefixes"
    prefix = prefixes[writer]
    assert branch.startswith(prefix), (
        f"current_branch '{branch}' does not start with prefix '{prefix}' "
        f"for current_writer '{writer}'"
    )


def test_qwen_phase_does_not_use_codex_prefix():
    """The current qwen branch must NOT start with codex/."""
    contract = _read_json("docs/architecture/architecture-contract.json")
    branch = contract["current_branch"]
    writer = contract["current_writer"]

    assert writer == "qwen"
    assert not branch.startswith("codex/"), (
        f"current_branch '{branch}' is a qwen branch but uses codex/ prefix"
    )


def test_all_developer_prefixes_are_unique():
    """Each developer in branch_prefixes must have a unique prefix."""
    contract = _read_json("docs/architecture/architecture-contract.json")
    prefixes = contract["branch_prefixes"]

    values = list(prefixes.values())
    assert len(values) == len(set(values)), (
        f"Duplicate branch prefixes found: {values}"
    )


def test_human_branch_requires_name():
    """The human prefix pattern must include a <name> placeholder."""
    contract = _read_json("docs/architecture/architecture-contract.json")
    prefixes = contract["branch_prefixes"]

    assert "human" in prefixes
    human_prefix = prefixes["human"]
    assert "<name>" in human_prefix, (
        f"human prefix must include <name> placeholder, got: {human_prefix}"
    )
