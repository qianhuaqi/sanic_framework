from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

import lingshu

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = (
    "lingshu.cli",
    "lingshu.core",
    "lingshu.extensions",
    "lingshu.http",
    "lingshu.record",
    "lingshu.runtime",
    "lingshu.server",
    "lingshu.testing",
)
PROVIDER_COMPONENTS = {
    "lingshu.cli",
    "lingshu.core",
    "lingshu.http",
    "lingshu.record",
    "lingshu.runtime",
}


def test_root_layout_has_no_src_directory() -> None:
    assert not (ROOT / "src").exists()
    assert (ROOT / "lingshu" / "__init__.py").is_file()


def test_project_metadata_matches_frozen_baseline() -> None:
    with (ROOT / "pyproject.toml").open("rb") as file:
        configuration = tomllib.load(file)

    project = configuration["project"]
    assert project["name"] == "lingshu"
    assert project["version"] == "0.1.0.dev0"
    assert project["requires-python"] == ">=3.12"
    assert project["license"] == "Apache-2.0"
    assert project["dependencies"] == []
    assert configuration["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["lingshu"]


def test_root_facade_is_an_explicit_placeholder() -> None:
    assert lingshu.__all__ == ()


def test_component_boundaries_are_importable() -> None:
    for module_name in COMPONENTS:
        module = importlib.import_module(module_name)
        if module_name in PROVIDER_COMPONENTS:
            assert module.__all__
        else:
            assert module.__all__ == ()
