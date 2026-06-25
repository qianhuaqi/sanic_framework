from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_no_python_cache_directories_are_tracked():
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked_cache_files = [
        path for path in result.stdout.splitlines()
        if "__pycache__" in path or path.endswith(".pyc")
    ]
    assert tracked_cache_files == []


def test_env_example_exists_and_real_env_is_ignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore


def test_legacy_project_files_are_not_reintroduced():
    legacy_paths = [
        ROOT / "language",
        ROOT / "config" / "config.ini",
        ROOT / "config" / "settings.py",
        ROOT / "app" / "language" / "__init__.py",
        ROOT / "app" / "language" / "zh-CN" / "__init__.py",
        ROOT / "app" / "language" / "zh-CN" / "ERROR" / "__init__.py",
        ROOT / "app" / "language" / "en-US" / "__init__.py",
        ROOT / "app" / "language" / "en-US" / "ERROR" / "__init__.py",
    ]

    assert [path.relative_to(ROOT).as_posix() for path in legacy_paths if path.exists()] == []
