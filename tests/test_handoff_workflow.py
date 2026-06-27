from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BRANCH = "codex/phase-c1-request-runtime"


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


def _write_handoff(repo: Path, work_commit: str, branch: str = BRANCH):
    handoff = repo / "docs" / "codex" / "HANDOFF.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        "# Development Handoff\n\n"
        "Updated at: 2026-06-26\n"
        "Location: office\n"
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
        "- Latest instruction: test handoff\n",
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
    work_commit = _run(["git", "rev-parse", "HEAD"], cwd=work).stdout.strip()

    (work / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts" / "resume-work.ps1", work / "scripts" / "resume-work.ps1")
    shutil.copy2(ROOT / "scripts" / "verify-handoff.ps1", work / "scripts" / "verify-handoff.ps1")
    _write_handoff(work, work_commit)
    _run(["git", "add", "scripts", "docs"], cwd=work)
    _run(["git", "commit", "-m", "add handoff"], cwd=work)
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
    assert "Current branch: codex/phase-c1-request-runtime" in result.stdout
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
    (work / "docs" / "codex" / "HANDOFF.md").unlink()
    _run(["git", "add", "docs/codex/HANDOFF.md"], cwd=work)
    _run(["git", "commit", "-m", "remove handoff"], cwd=work)
    _run(["git", "push", "github", BRANCH], cwd=work)

    result = _powershell(work / "scripts" / "verify-handoff.ps1", work)

    assert result.returncode != 0
    assert "HANDOFF.md is missing" in result.stderr


def test_verify_handoff_fails_when_work_commit_is_not_ancestor(tmp_path):
    work = _prepare_handoff_repo(tmp_path)
    _write_handoff(work, "f" * 40)
    _run(["git", "add", "docs/codex/HANDOFF.md"], cwd=work)
    _run(["git", "commit", "-m", "invalid work commit"], cwd=work)
    _run(["git", "push", "github", BRANCH], cwd=work)

    result = _powershell(work / "scripts" / "verify-handoff.ps1", work)

    assert result.returncode != 0
    assert "does not exist" in result.stderr or "not an ancestor" in result.stderr


def test_handoff_scripts_use_github_remote_and_fail_closed_checks():
    resume = _read("scripts/resume-work.ps1")
    verify = _read("scripts/verify-handoff.ps1")
    combined = f"{resume}\n{verify}"

    assert '"github"' in combined
    assert "Assert-CleanWorktree" in combined
    assert "Assert-HeadMatchesRemote" in combined
    assert "docs/codex/HANDOFF.md is missing" in combined
    assert "status\", \"--porcelain\"" in combined
    assert "\"rev-parse\"" in verify
    assert "github/$Branch" in verify


def test_agents_records_single_writer_rule_and_sources_of_truth():
    agents = _read("AGENTS.md")

    assert "GitHub remote is always `github`" in agents
    assert "A phase branch may be written by only one computer at a time." in agents
    assert "Codex chat history is not a source of truth." in agents
    assert "Business code must not import `lingshu.system`." in agents
    assert "Do not start phases C2, C3, C4, C5, C6, D, E, or F." in agents


def test_current_phase_and_handoff_docs_exist_with_current_context():
    current_phase = _read("docs/codex/CURRENT_PHASE.md")
    handoff = _read("docs/codex/HANDOFF.md")

    assert "Current phase: C1" in current_phase
    assert "Current branch: codex/phase-c1-request-runtime" in current_phase
    assert "Current issue: #12" in current_phase
    assert "Next phase allowed: no" in current_phase
    assert "Branch:" in handoff
    assert "Work commit:" in handoff
    assert "Local HEAD:" not in handoff
    assert "Remote HEAD:" not in handoff
    assert "pending" not in handoff


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
