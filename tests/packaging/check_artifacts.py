from __future__ import annotations

import argparse
import email
import tarfile
import zipfile
from pathlib import Path

FORBIDDEN_PARTS = {
    ".env",
    ".git",
    ".github",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "credentials",
    "tests",
    "tools",
}


def _wheel_inventory(path: Path) -> tuple[set[str], bytes]:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
        wheel_name = next(name for name in names if name.endswith(".dist-info/WHEEL"))
        metadata_bytes = archive.read(metadata_name)
        metadata = email.message_from_bytes(metadata_bytes)
        wheel_text = archive.read(wheel_name).decode("utf-8")

    assert path.name.endswith("-py3-none-any.whl"), path.name
    assert metadata["Name"] == "lingshu"
    assert metadata["Version"] == "0.1.0.dev0"
    assert metadata["Requires-Python"] == ">=3.12"
    assert (metadata.get("License-Expression") or metadata.get("License")) == "Apache-2.0"
    assert "Tag: py3-none-any" in wheel_text

    requirements = metadata.get_all("Requires-Dist", [])
    assert all("extra == 'dev'" in value or 'extra == "dev"' in value for value in requirements)

    assert any(name == "lingshu/__init__.py" for name in names)
    assert any(name == "lingshu/py.typed" for name in names)
    assert any(name.endswith(".dist-info/licenses/LICENSE") for name in names)
    assert any(name.endswith(".dist-info/licenses/NOTICE") for name in names)

    for name in names:
        parts = {part.lower() for part in Path(name).parts}
        assert not parts.intersection(FORBIDDEN_PARTS), name
        assert name.startswith("lingshu/") or ".dist-info/" in name, name

    comparable = {name for name in names if not name.endswith(".dist-info/RECORD")}
    return comparable, metadata_bytes


def _validate_sdist(path: Path) -> None:
    with tarfile.open(path, "r:gz") as archive:
        names = archive.getnames()

    assert any(name.endswith("/pyproject.toml") for name in names)
    assert any(name.endswith("/README.md") for name in names)
    assert any(name.endswith("/LICENSE") for name in names)
    assert any(name.endswith("/NOTICE") for name in names)
    assert any(name.endswith("/lingshu/__init__.py") for name in names)
    assert not any("/.env" in name or "/__pycache__/" in name for name in names)


def validate(directory: Path) -> None:
    wheels = sorted(directory.glob("*.whl"))
    sdists = sorted(directory.glob("*.tar.gz"))
    assert len(wheels) == 1, wheels
    assert len(sdists) == 1, sdists
    _wheel_inventory(wheels[0])
    _validate_sdist(sdists[0])


def compare(first: Path, second: Path) -> None:
    first_inventory, first_metadata = _wheel_inventory(first)
    second_inventory, second_metadata = _wheel_inventory(second)
    assert first_inventory == second_inventory
    assert first_metadata == second_metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("directory", type=Path)
    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("first", type=Path)
    compare_parser.add_argument("second", type=Path)
    arguments = parser.parse_args()

    if arguments.command == "validate":
        validate(arguments.directory)
    else:
        compare(arguments.first, arguments.second)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
