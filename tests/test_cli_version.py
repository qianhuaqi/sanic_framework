from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

EXPECTED = "lingshu 0.1.0.dev0"


def _environment_without_pythonpath() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    return environment


def test_module_version_outside_checkout(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "lingshu", "--version"],
        cwd=tmp_path,
        env=_environment_without_pythonpath(),
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == EXPECTED


def test_version_subcommand_outside_checkout(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "lingshu", "version"],
        cwd=tmp_path,
        env=_environment_without_pythonpath(),
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == EXPECTED


def test_console_script_reports_installed_version(tmp_path: Path) -> None:
    executable = shutil.which("lingshu")
    assert executable is not None
    result = subprocess.run(
        [executable, "--version"],
        cwd=tmp_path,
        env=_environment_without_pythonpath(),
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == EXPECTED
