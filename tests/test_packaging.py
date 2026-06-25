from pathlib import Path
import tomllib

from framework.cli.project import SCAFFOLD_DIR


ROOT = Path(__file__).resolve().parents[1]


def _pyproject():
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_pyproject_exposes_framework_cli_and_python_contract():
    pyproject = _pyproject()

    assert pyproject["project"]["requires-python"] == ">=3.10,<3.15"
    assert pyproject["project"]["scripts"]["sanic-framework"] == "framework.cli.main:main"
    assert "Framework :: Sanic" in pyproject["project"]["classifiers"]


def test_pyproject_packages_framework_scaffold_templates():
    pyproject = _pyproject()
    package_data = pyproject["tool"]["setuptools"]["package-data"]["framework"]

    assert "modules.ini" in package_data
    assert "scaffold/*.j2" in package_data
    assert (SCAFFOLD_DIR / "env.example.j2").exists()
    assert (SCAFFOLD_DIR / "README.md.j2").exists()
    assert (SCAFFOLD_DIR / "docker-compose.yml.j2").exists()
