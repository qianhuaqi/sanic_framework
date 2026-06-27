from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BRANCH = "qwen/phase-c2-rc-development-constitution"
WRITER = "qwen"


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _run(command: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise AssertionError(f"{command} failed\nstdout={result.stdout}\nstderr={result.stderr}")
    return result


def _powershell(script: Path, cwd: Path, branch: str = BRANCH) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-Branch",
            branch,
        ],
        cwd=cwd,
        check=False,
    )


def _write_current_phase(repo: Path, branch: str = BRANCH, writer: str = WRITER):
    content = (
        "# Current Phase\n\n"
        f"Current branch: {branch}\n"
        f"Current writer: {writer}\n"
        "Current issue: #21-test\n"
        "Status: in progress\n"
        "Next phase allowed: no\n\n"
        "## Test\n"
        "- test\n"
    )
    phase_file = repo / "docs" / "development" / "CURRENT_PHASE.md"
    phase_file.parent.mkdir(parents=True, exist_ok=True)
    phase_file.write_text(content, encoding="utf-8")


def _write_contract(repo: Path):
    content = (
        "{\n"
        '  "schema_version": "1.0.0",\n'
        '  "constitution_version": "1.0",\n'
        '  "status": "proposed",\n'
        '  "effective_on": "c2-rc-pr-merge",\n'
        '  "branch_prefixes": {\n'
        '    "codex": "codex/phase-",\n'
        '    "qwen": "qwen/phase-",\n'
        '    "gemini": "gemini/phase-",\n'
        '    "glm": "glm/phase-",\n'
        '    "claude": "claude/phase-",\n'
        '    "human": "human/<name>/phase-"\n'
        "  }\n"
        "}\n"
    )
    contract_file = repo / "docs" / "architecture" / "architecture-contract.json"
    contract_file.parent.mkdir(parents=True, exist_ok=True)
    contract_file.write_text(content, encoding="utf-8")


def _write_handoff(repo: Path, work_commit: str, branch: str = BRANCH, writer: str = WRITER):
    """Write the canonical handoff to docs/development/HANDOFF.md only.

    Does NOT write docs/codex/HANDOFF.md — that is written separately.
    """
    content = (
        "# Development Handoff\n\n"
        "Updated at: 2026-06-26\n"
        "Location: office\n"
        f"Writer: {writer}\n"
        f"Branch: {branch}\n"
        "Worktree: clean\n"
        f"Work commit: {work_commit}\n\n"
        "## Completed\n"
        "- baseline\n\n"
        "## Remaining\n"
        "- continue\n\n"
        "## Last verification\n"
        "- pytest: not run\n"
        "- contract check: not run\n"
        "- build: not run\n"
        "- diff check: not run\n\n"
        "## Known risks\n"
        "- none\n\n"
        "## Next exact action\n"
        "- continue\n\n"
        "## Current PR\n"
        "- PR: #12-test\n"
        "- Latest instruction: test handoff\n"
    )
    dev_handoff = repo / "docs" / "development" / "HANDOFF.md"
    dev_handoff.parent.mkdir(parents=True, exist_ok=True)
    dev_handoff.write_text(content, encoding="utf-8")


def _write_codex_pointers(repo: Path):
    """Write compatibility pointers for codex docs."""
    codex_handoff = repo / "docs" / "codex" / "HANDOFF.md"
    codex_handoff.parent.mkdir(parents=True, exist_ok=True)
    codex_handoff.write_text(
        "# Development Handoff (Compatibility Pointer)\n\n"
        "This file has moved to the model-agnostic development directory.\n\n"
        "**Current fact source:** `docs/development/HANDOFF.md`\n",
        encoding="utf-8",
    )


def _prepare_handoff_repo(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    _run(["git", "init", "--bare", str(remote)], cwd=tmp_path)
    _run(["git", "clone", str(remote), str(work)], cwd=tmp_path)
    _run(["git", "remote", "rename", "origin", "github"], cwd=work)
    _run(["git", "config", "user.email", "test@example.invalid"], cwd=work)
    _run(["git", "config", "user.name", "Handoff Test"], cwd=work)
    _run(["git", "switch", "-c", BRANCH], cwd=work)
    (work / "README.md").write_text("handoff test\n", encoding="utf-8")
    _run(["git", "add", "README.md"], cwd=work)
    _run(["git", "commit", "-m", "initial"], cwd=work)

    (work / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts" / "resume-work.ps1", work / "scripts" / "resume-work.ps1")
    shutil.copy2(ROOT / "scripts" / "verify-handoff.ps1", work / "scripts" / "verify-handoff.ps1")

    (work / "docs" / "development").mkdir(parents=True, exist_ok=True)
    _write_current_phase(work)
    _write_contract(work)
    _write_codex_pointers(work)
    _run(["git", "add", "scripts", "docs"], cwd=work)
    _run(["git", "commit", "-m", "add scripts and phase docs"], cwd=work)

    # Work commit = last implementation commit (scripts + docs, but NOT HANDOFF)
    work_commit = _run(["git", "rev-parse", "HEAD"], cwd=work).stdout.strip()

    # Now write HANDOFF only and commit as the handoff-only commit
    _write_handoff(work, work_commit)
    _run(["git", "add", "docs/development/HANDOFF.md"], cwd=work)
    _run(["git", "commit", "-m", "finalize handoff"], cwd=work)
    _run(["git", "push", "-u", "github", BRANCH], cwd=work)
    return work


def test_handoff_scripts_exist():
    assert (ROOT / "scripts" / "resume-work.ps1").exists()
    assert (ROOT / "scripts" / "verify-handoff.ps1").exists()
    assert (ROOT / "scripts" / "setup-dev.ps1").exists()


def test_handoff_scripts_avoid_disallowed_git_operations():
    script_text = "\n".join(
        [
            _read("scripts/resume-work.ps1"),
            _read("scripts/verify-handoff.ps1"),
        ]
    ).lower()

    forbidden = [
        "reset --hard",
        "clean -fd",
        "push --force",
        "rebase",
        "stash",
    ]
    assert [term for term in forbidden if term in script_text] == []


def test_verify_handoff_passes_in_real_git_repo(tmp_path):
    work = _prepare_handoff_repo(tmp_path)
    result = _powershell(work / "scripts" / "verify-handoff.ps1", work)
    assert result.returncode == 0, result.stderr
    assert "Handoff verification passed" in result.stdout


def test_resume_work_passes_in_real_git_repo(tmp_path):
    work = _prepare_handoff_repo(tmp_path)
    result = _powershell(work / "scripts" / "resume-work.ps1", work)
    assert result.returncode == 0, result.stderr
    assert f"Current branch: {BRANCH}" in result.stdout
    assert "HANDOFF.md:" in result.stdout


def test_resume_work_fails_when_worktree_is_dirty(tmp_path):
    work = _prepare_handoff_repo(tmp_path)
    (work / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    result = _powershell(work / "scripts" / "resume-work.ps1", work)
    assert result.returncode != 0
    assert "Worktree is dirty" in result.stderr


def test_verify_handoff_fails_when_local_head_differs_from_remote(tmp_path):
    work = _prepare_handoff_repo(tmp_path)
    (work / "local.txt").write_text("local only\n", encoding="utf-8")
    _run(["git", "add", "local.txt"], cwd=work)
    _run(["git", "commit", "-m", "local only"], cwd=work)
    result = _powershell(work / "scripts" / "verify-handoff.ps1", work)
    assert result.returncode != 0
    assert "does not match" in result.stderr


def test_verify_handoff_fails_when_handoff_is_missing(tmp_path):
    work = _prepare_handoff_repo(tmp_path)
    (work / "docs" / "development" / "HANDOFF.md").unlink()
    _run(["git", "add", "docs/development/HANDOFF.md"], cwd=work)
    _run(["git", "commit", "-m", "remove handoff"], cwd=work)
    _run(["git", "push", "github", BRANCH], cwd=work)
    result = _powershell(work / "scripts" / "verify-handoff.ps1", work)
    assert result.returncode != 0
    assert "docs/development/HANDOFF.md is missing" in result.stderr


def test_scripts_work_with_only_dev_handoff_and_codex_pointer(tmp_path):
    work = _prepare_handoff_repo(tmp_path)
    verify_result = _powershell(work / "scripts" / "verify-handoff.ps1", work)
    assert verify_result.returncode == 0, verify_result.stderr
    resume_result = _powershell(work / "scripts" / "resume-work.ps1", work)
    assert resume_result.returncode == 0, resume_result.stderr
    assert f"Current branch: {BRANCH}" in resume_result.stdout


def test_deleting_dev_handoff_causes_fail_closed(tmp_path):
    work = _prepare_handoff_repo(tmp_path)
    (work / "docs" / "development" / "HANDOFF.md").unlink()
    fake_codex = work / "docs" / "codex" / "HANDOFF.md"
    fake_codex.write_text(
        "# Development Handoff\n\n"
        f"Branch: {BRANCH}\n"
        "Worktree: clean\n"
        f"Work commit: {_run(['git', 'rev-parse', 'HEAD'], cwd=work).stdout.strip()}\n",
        encoding="utf-8",
    )
    _run(["git", "add", "docs"], cwd=work)
    _run(["git", "commit", "-m", "remove dev handoff, keep fake codex"], cwd=work)
    _run(["git", "push", "github", BRANCH], cwd=work)
    result = _powershell(work / "scripts" / "verify-handoff.ps1", work)
    assert result.returncode != 0
    assert "docs/development/HANDOFF.md is missing" in result.stderr


def test_verify_handoff_fails_when_work_commit_is_not_ancestor(tmp_path):
    work = _prepare_handoff_repo(tmp_path)
    _write_handoff(work, "f" * 40)
    _run(["git", "add", "docs"], cwd=work)
    _run(["git", "commit", "-m", "invalid work commit"], cwd=work)
    _run(["git", "push", "github", BRANCH], cwd=work)
    result = _powershell(work / "scripts" / "verify-handoff.ps1", work)
    assert result.returncode != 0
    assert "does not exist" in result.stderr or "not an ancestor" in result.stderr


def test_verify_handoff_fails_when_writer_branch_mismatch(tmp_path):
    """writer=qwen but branch=codex/... must fail."""
    work = _prepare_handoff_repo(tmp_path)

    # Rewrite CURRENT_PHASE with mismatched writer/branch
    _write_current_phase(work, branch="codex/phase-test", writer="qwen")
    _run(["git", "add", "docs/development/CURRENT_PHASE.md"], cwd=work)
    _run(["git", "commit", "-m", "phase update"], cwd=work)

    # New work_commit includes the phase change
    new_wc = _run(["git", "rev-parse", "HEAD"], cwd=work).stdout.strip()
    _write_handoff(work, new_wc, branch="codex/phase-test", writer="qwen")
    _run(["git", "add", "docs/development/HANDOFF.md"], cwd=work)
    _run(["git", "commit", "-m", "handoff update"], cwd=work)
    _run(["git", "switch", "-c", "codex/phase-test"], cwd=work)
    _run(["git", "push", "-u", "github", "codex/phase-test"], cwd=work)

    result = _powershell(work / "scripts" / "verify-handoff.ps1", work, branch="codex/phase-test")
    assert result.returncode != 0, result.stderr
    assert "does not start with prefix" in result.stderr


def test_verify_handoff_fails_when_writer_not_registered(tmp_path):
    """An unregistered writer must cause fail-closed."""
    work = _prepare_handoff_repo(tmp_path)
    _write_current_phase(work, writer="unknowndev")
    _run(["git", "add", "docs/development/CURRENT_PHASE.md"], cwd=work)
    _run(["git", "commit", "-m", "phase update"], cwd=work)
    new_wc = _run(["git", "rev-parse", "HEAD"], cwd=work).stdout.strip()
    _write_handoff(work, new_wc, writer="unknowndev")
    _run(["git", "add", "docs/development/HANDOFF.md"], cwd=work)
    _run(["git", "commit", "-m", "handoff update"], cwd=work)
    _run(["git", "push", "github", BRANCH], cwd=work)

    result = _powershell(work / "scripts" / "verify-handoff.ps1", work)
    assert result.returncode != 0
    assert "not registered" in result.stderr


def test_verify_handoff_fails_when_handoff_writer_differs_from_phase(tmp_path):
    """HANDOFF Writer and CURRENT_PHASE Current writer must match."""
    work = _prepare_handoff_repo(tmp_path)
    new_wc = _run(["git", "rev-parse", "HEAD"], cwd=work).stdout.strip()
    _write_handoff(work, new_wc, writer="codex")
    _run(["git", "add", "docs/development/HANDOFF.md"], cwd=work)
    _run(["git", "commit", "-m", "writer mismatch"], cwd=work)
    _run(["git", "push", "github", BRANCH], cwd=work)

    result = _powershell(work / "scripts" / "verify-handoff.ps1", work)
    assert result.returncode != 0
    assert "!=" in result.stderr


def test_verify_handoff_fails_when_handoff_branch_differs_from_phase(tmp_path):
    """HANDOFF Branch and CURRENT_PHASE Current branch must match."""
    work = _prepare_handoff_repo(tmp_path)
    hc = _run(["git", "rev-parse", "HEAD"], cwd=work).stdout.strip()
    (work / "docs" / "development" / "HANDOFF.md").write_text(
        f"# Development Handoff\n\nWriter: qwen\nBranch: qwen/phase-wrong\n"
        f"Worktree: clean\nWork commit: {hc}\n",
        encoding="utf-8",
    )
    _run(["git", "add", "docs/development/HANDOFF.md"], cwd=work)
    _run(["git", "commit", "-m", "branch mismatch"], cwd=work)
    _run(["git", "push", "github", BRANCH], cwd=work)

    result = _powershell(work / "scripts" / "verify-handoff.ps1", work)
    assert result.returncode != 0


def test_verify_handoff_fails_when_extra_files_after_work_commit(tmp_path):
    """HEAD..Work commit must only change docs/development/HANDOFF.md."""
    work = _prepare_handoff_repo(tmp_path)
    # The initial setup already has the scripts commit as the HEAD.
    # Add a non-HANDOFF change after the work commit.
    (work / "extra.txt").write_text("extra\n", encoding="utf-8")
    _run(["git", "add", "extra.txt"], cwd=work)
    _run(["git", "commit", "-m", "extra file"], cwd=work)
    _run(["git", "push", "github", BRANCH], cwd=work)

    # Now update HANDOFF with a handoff commit (so HEAD != work commit)
    hc = _run(["git", "rev-parse", "HEAD"], cwd=work).stdout.strip()
    _write_handoff(work, hc)
    _run(["git", "add", "docs/development/HANDOFF.md"], cwd=work)
    _run(["git", "commit", "-m", "update handoff only"], cwd=work)
    _run(["git", "push", "github", BRANCH], cwd=work)

    result = _powershell(work / "scripts" / "verify-handoff.ps1", work)
    # Should pass because the diff from work_commit to HEAD only contains HANDOFF.md
    assert result.returncode == 0, result.stderr


def test_verify_handoff_fails_when_non_handoff_file_in_work_to_head_diff(tmp_path):
    """If work_commit..HEAD contains a non-HANDOFF file, must fail."""
    work = _prepare_handoff_repo(tmp_path)
    wc = _run(["git", "rev-parse", "HEAD"], cwd=work).stdout.strip()

    # Add a non-HANDOFF file AND update HANDOFF (so diff has 2 files)
    (work / "extra2.txt").write_text("extra2\n", encoding="utf-8")
    _write_handoff(work, wc)
    _run(["git", "add", "extra2.txt", "docs/development/HANDOFF.md"], cwd=work)
    _run(["git", "commit", "-m", "extra + handoff update"], cwd=work)
    _run(["git", "push", "github", BRANCH], cwd=work)

    result = _powershell(work / "scripts" / "verify-handoff.ps1", work)
    assert result.returncode != 0
    assert "HANDOFF.md" in result.stderr


def test_handoff_scripts_use_github_remote_and_fail_closed_checks():
    resume = _read("scripts/resume-work.ps1")
    verify = _read("scripts/verify-handoff.ps1")
    combined = f"{resume}\n{verify}"

    assert '"github"' in combined
    assert "Assert-CleanWorktree" in combined
    assert "Assert-HeadMatchesRemote" in combined
    assert "docs/development/HANDOFF.md is missing" in combined
    assert "Assert-WriterBranchCrossCheck" in combined
    assert "Assert-HandoffOnlyChangesHandoff" in combined
    assert "branch_prefixes" in combined
    assert "Current writer" in combined


def test_agents_records_single_writer_rule_and_sources_of_truth():
    agents = _read("AGENTS.md")
    assert "github" in agents
    assert "one writer at a time" in agents.lower()
    assert "Sources Of Truth" in agents
    assert "NOT sources of truth" in agents
    assert "docs/development/DEVELOPMENT_CONSTITUTION.md" in agents
    assert "Phase C1 Boundaries" not in agents


def test_current_phase_and_handoff_docs_exist_with_current_context():
    current_phase = _read("docs/development/CURRENT_PHASE.md")
    handoff = _read("docs/development/HANDOFF.md")

    assert "Current phase: C2-RC" in current_phase
    assert "qwen/phase-c2-rc-development-constitution" in current_phase
    assert "Current writer: qwen" in current_phase
    assert "Current issue: #21" in current_phase
    assert "Next phase allowed: no" in current_phase
    assert "Branch:" in handoff
    assert "Writer:" in handoff
    assert "Worktree:" in handoff


def test_readme_contains_cross_device_handoff_flow():
    readme = _read("README.md")
    assert "## Cross-Device Handoff" in readme
    assert "## Local Development Setup" in readme
    assert "scripts\\setup-dev.ps1" in readme
    assert "scripts\\resume-work.ps1" in readme
    assert "scripts\\verify-handoff.ps1" in readme
    assert "[WORKING]" in readme
    assert "[HANDOFF]" in readme
    assert "office" in readme
    assert "home" in readme


def test_scaffold_readme_contains_install_and_startup_guidance():
    scaffold_readme = _read("src/lingshu/scaffold/README.md.j2")
    assert 'python -m pip install -e ".[dev]"' in scaffold_readme
    assert "python run.py" in scaffold_readme
    assert "working directory to the project root" in scaffold_readme
    assert "PyCharm" in scaffold_readme


def test_handoff_docs_do_not_contain_obvious_secret_examples():
    paths = [
        "AGENTS.md",
        "docs/development/CURRENT_PHASE.md",
        "docs/development/HANDOFF.md",
        "docs/codex/CURRENT_PHASE.md",
        "docs/codex/HANDOFF.md",
        "README.md",
        "scripts/setup-dev.ps1",
        "scripts/resume-work.ps1",
        "scripts/verify-handoff.ps1",
    ]
    combined = "\n".join(_read(path) for path in paths)
    risky_patterns = [
        r"gh[pousr]_[A-Za-z0-9_]{20,}",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"sk-[A-Za-z0-9]{20,}",
        r"(?i)codex[_-]?token\s*=",
        r"(?i)password\s*=\s*['\"][^'\"]+['\"]",
    ]
    assert [pattern for pattern in risky_patterns if re.search(pattern, combined)] == []


def test_old_codex_docs_are_compatibility_pointers():
    codex_phase = _read("docs/codex/CURRENT_PHASE.md")
    codex_handoff = _read("docs/codex/HANDOFF.md")
    assert "docs/development/CURRENT_PHASE.md" in codex_phase
    assert "docs/development/HANDOFF.md" in codex_handoff
    assert "Compatibility Pointer" in codex_phase
    assert "Compatibility Pointer" in codex_handoff


# ---------------------------------------------------------------------------
# Human branch regression tests
# ---------------------------------------------------------------------------

HUMAN_BRANCH = "human/alice/phase-c2-r1-auth"


def _prepare_human_repo(tmp_path: Path, branch: str = HUMAN_BRANCH) -> Path:
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    _run(["git", "init", "--bare", str(remote)], cwd=tmp_path)
    _run(["git", "clone", str(remote), str(work)], cwd=tmp_path)
    _run(["git", "remote", "rename", "origin", "github"], cwd=work)
    _run(["git", "config", "user.email", "test@example.invalid"], cwd=work)
    _run(["git", "config", "user.name", "Handoff Test"], cwd=work)
    _run(["git", "switch", "-c", branch], cwd=work)
    (work / "README.md").write_text("handoff test\n", encoding="utf-8")
    _run(["git", "add", "README.md"], cwd=work)
    _run(["git", "commit", "-m", "initial"], cwd=work)

    (work / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts" / "resume-work.ps1", work / "scripts" / "resume-work.ps1")
    shutil.copy2(ROOT / "scripts" / "verify-handoff.ps1", work / "scripts" / "verify-handoff.ps1")

    (work / "docs" / "development").mkdir(parents=True, exist_ok=True)
    phase_content = (
        "# Current Phase\n\n"
        f"Current branch: {branch}\n"
        "Current writer: human\n"
        "Current issue: #99\n"
        "Status: in progress\n"
        "Next phase allowed: no\n"
    )
    (work / "docs" / "development" / "CURRENT_PHASE.md").write_text(phase_content, encoding="utf-8")
    _write_codex_pointers(work)
    _write_contract(work)
    _run(["git", "add", "scripts", "docs"], cwd=work)
    _run(["git", "commit", "-m", "add docs"], cwd=work)
    work_commit = _run(["git", "rev-parse", "HEAD"], cwd=work).stdout.strip()
    _write_handoff(work, work_commit, branch=branch, writer="human")
    _run(["git", "add", "docs/development/HANDOFF.md"], cwd=work)
    _run(["git", "commit", "-m", "handoff"], cwd=work)
    _run(["git", "push", "-u", "github", branch], cwd=work)
    return work


def test_human_branch_with_valid_name_passes(tmp_path):
    """human/alice/phase-c2-r1-auth must pass."""
    work = _prepare_human_repo(tmp_path)
    result = _powershell(work / "scripts" / "verify-handoff.ps1", work, branch=HUMAN_BRANCH)
    assert result.returncode == 0, result.stderr
    assert "Handoff verification passed" in result.stdout


def test_human_branch_empty_name_rejected_by_regex():
    """human//phase-c2-r1-auth must fail the regex check.

    Git itself rejects double-slash branch names, so we test the script's
    regex logic directly instead of creating a real branch.
    """
    verify = _read("scripts/verify-handoff.ps1")
    resume = _read("scripts/resume-work.ps1")

    # Both scripts must use the strict regex with negative lookahead, NOT a -replace approach
    assert '"^human/(?!phase-)[^/]+/phase-[^/]+$"' in verify
    assert '"^human/(?!phase-)[^/]+/phase-[^/]+$"' in resume
    # Must NOT use the old -replace approach
    assert '-replace "<name>", ""' not in verify
    assert '-replace "<name>", ""' not in resume
    # Must NOT use the old regex without lookahead
    assert '"^human/[^/]+/phase-[^/]+$"' not in verify
    assert '"^human/[^/]+/phase-[^/]+$"' not in resume

    # The regex ^human/(?!phase-)[^/]+/phase-[^/]+$ does NOT match:
    import re
    pattern = r"^human/(?!phase-)[^/]+/phase-[^/]+$"
    assert not re.match(pattern, "human//phase-c2-r1-auth")  # empty name
    assert not re.match(pattern, "human/phase-c2-r1-auth")   # missing name
    assert not re.match(pattern, "human/alice/not-phase-x")  # no phase-
    assert not re.match(pattern, "human/phase-bot/phase-c2-r1-auth")  # name starts with phase-
    # But DOES match valid:
    assert re.match(pattern, "human/alice/phase-c2-r1-auth")


def test_human_branch_missing_name_segment_fails(tmp_path):
    """human/phase-c2-r1-auth (missing name) must fail."""
    bad_branch = "human/phase-c2-r1-auth"
    work = _prepare_human_repo(tmp_path, branch=bad_branch)
    result = _powershell(work / "scripts" / "verify-handoff.ps1", work, branch=bad_branch)
    assert result.returncode != 0
    assert "must match human/" in result.stderr


def test_human_branch_no_phase_segment_fails(tmp_path):
    """human/alice/not-phase-x must fail (no /phase- segment)."""
    bad_branch = "human/alice/not-phase-x"
    work = _prepare_human_repo(tmp_path, branch=bad_branch)
    result = _powershell(work / "scripts" / "verify-handoff.ps1", work, branch=bad_branch)
    assert result.returncode != 0
    assert "must match human/" in result.stderr


def test_human_branch_name_starting_with_phase_fails(tmp_path):
    """human/phase-bot/phase-c2-r1-auth must fail (name starts with 'phase-')."""
    bad_branch = "human/phase-bot/phase-c2-r1-auth"
    work = _prepare_human_repo(tmp_path, branch=bad_branch)
    result = _powershell(work / "scripts" / "verify-handoff.ps1", work, branch=bad_branch)
    assert result.returncode != 0
    assert "must match human/" in result.stderr


# ---------------------------------------------------------------------------
# Research branch regression tests
# ---------------------------------------------------------------------------

RESEARCH_BRANCH = "research/src-audit"


def _prepare_research_repo(
    tmp_path: Path,
    branch: str = RESEARCH_BRANCH,
    phase_type: str = "non-implementation research",
) -> Path:
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    _run(["git", "init", "--bare", str(remote)], cwd=tmp_path)
    _run(["git", "clone", str(remote), str(work)], cwd=tmp_path)
    _run(["git", "remote", "rename", "origin", "github"], cwd=work)
    _run(["git", "config", "user.email", "test@example.invalid"], cwd=work)
    _run(["git", "config", "user.name", "Handoff Test"], cwd=work)
    _run(["git", "switch", "-c", branch], cwd=work)
    (work / "README.md").write_text("research test\n", encoding="utf-8")
    _run(["git", "add", "README.md"], cwd=work)
    _run(["git", "commit", "-m", "initial"], cwd=work)

    (work / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts" / "resume-work.ps1", work / "scripts" / "resume-work.ps1")
    shutil.copy2(ROOT / "scripts" / "verify-handoff.ps1", work / "scripts" / "verify-handoff.ps1")

    (work / "docs" / "development").mkdir(parents=True, exist_ok=True)
    phase_lines = [
        "# Current Phase\n\n",
        f"Current branch: {branch}\n",
        "Current writer: qwen\n",
        "Current issue: #88\n",
        "Status: in progress\n",
        "Next phase allowed: no\n",
    ]
    if phase_type is not None:
        phase_lines.append(f"Phase type: {phase_type}\n")
    (work / "docs" / "development" / "CURRENT_PHASE.md").write_text(
        "".join(phase_lines), encoding="utf-8"
    )
    _write_codex_pointers(work)
    _write_contract(work)
    _run(["git", "add", "scripts", "docs"], cwd=work)
    _run(["git", "commit", "-m", "add docs"], cwd=work)
    work_commit = _run(["git", "rev-parse", "HEAD"], cwd=work).stdout.strip()
    _write_handoff(work, work_commit, branch=branch, writer="qwen")
    _run(["git", "add", "docs/development/HANDOFF.md"], cwd=work)
    _run(["git", "commit", "-m", "handoff"], cwd=work)
    _run(["git", "push", "-u", "github", branch], cwd=work)
    return work


def test_research_branch_with_correct_phase_type_passes(tmp_path):
    """writer=qwen + research/src-audit + correct Phase type must pass."""
    work = _prepare_research_repo(tmp_path)
    result = _powershell(work / "scripts" / "verify-handoff.ps1", work, branch=RESEARCH_BRANCH)
    assert result.returncode == 0, result.stderr
    assert "Handoff verification passed" in result.stdout


def test_research_branch_missing_phase_type_fails(tmp_path):
    """research branch without Phase type must fail."""
    work = _prepare_research_repo(tmp_path, phase_type=None)
    result = _powershell(work / "scripts" / "verify-handoff.ps1", work, branch=RESEARCH_BRANCH)
    assert result.returncode != 0
    assert "Phase type" in result.stderr


def test_research_branch_wrong_phase_type_fails(tmp_path):
    """research branch with wrong Phase type must fail."""
    work = _prepare_research_repo(tmp_path, phase_type="implementation")
    result = _powershell(work / "scripts" / "verify-handoff.ps1", work, branch=RESEARCH_BRANCH)
    assert result.returncode != 0
    assert "non-implementation research" in result.stderr


def test_research_branch_empty_slug_rejected_by_regex():
    """research/ (empty slug) must fail the regex check.

    Git itself rejects trailing-slash branch names, so we test the script's
    regex logic directly.
    """
    verify = _read("scripts/verify-handoff.ps1")
    resume = _read("scripts/resume-work.ps1")

    # Both scripts must use the research slug regex
    assert '"^research/[^/]+$"' in verify
    assert '"^research/[^/]+$"' in resume

    import re
    pattern = r"^research/[^/]+$"
    assert not re.match(pattern, "research/")        # empty slug
    assert not re.match(pattern, "research/foo/bar")  # multi-segment slug
    assert re.match(pattern, "research/src-audit")    # valid
