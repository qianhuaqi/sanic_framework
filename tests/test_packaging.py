from pathlib import Path
import subprocess
import sys
import zipfile
import tomllib

from lingshu.cli.project import SCAFFOLD_DIR


ROOT = Path(__file__).resolve().parents[1]


def _pyproject():
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_pyproject_exposes_lingshu_cli_and_python_contract():
    pyproject = _pyproject()

    assert pyproject["project"]["name"] == "lingshu-framework"
    assert pyproject["project"]["requires-python"] == ">=3.10,<3.15"
    assert pyproject["project"]["scripts"]["lingshu"] == "lingshu.cli.main:main"
    assert "sanic-framework" not in pyproject["project"]["scripts"]
    assert "Framework :: Sanic" in pyproject["project"]["classifiers"]


def test_pyproject_packages_lingshu_scaffold_templates():
    pyproject = _pyproject()
    package_data = pyproject["tool"]["setuptools"]["package-data"]["lingshu"]

    assert pyproject["tool"]["setuptools"]["package-dir"] == {"": "src"}
    assert pyproject["tool"]["setuptools"]["packages"]["find"]["where"] == ["src"]
    assert pyproject["tool"]["setuptools"]["packages"]["find"]["include"] == ["lingshu*"]
    assert "resources/error_codes/*.ini" in package_data
    assert "language/**/*.ini" in package_data
    assert "scaffold/*.j2" in package_data
    assert (ROOT / "src" / "lingshu" / "resources" / "error_codes" / "modules.ini").exists()
    assert (SCAFFOLD_DIR / "pyproject.toml.j2").exists()
    assert (SCAFFOLD_DIR / "env.example.j2").exists()
    assert (SCAFFOLD_DIR / "README.md.j2").exists()
    assert (SCAFFOLD_DIR / "docker-compose.yml.j2").exists()


def test_built_wheel_contains_lingshu_package_data_and_no_legacy_framework(tmp_path):
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path)],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    wheels = sorted(tmp_path.glob("lingshu_framework-*.whl"))
    assert wheels, "run python -m build before this packaging smoke test"

    with zipfile.ZipFile(wheels[-1]) as archive:
        names = set(archive.namelist())

    assert "lingshu/resources/error_codes/modules.ini" in names
    assert "lingshu/scaffold/pyproject.toml.j2" in names
    assert "lingshu/scaffold/README.md.j2" in names
    assert "lingshu/scaffold/env.example.j2" in names
    assert "lingshu/language/zh-CN/ERROR/system.ini" in names
    assert "lingshu/language/en-US/ERROR/system.ini" in names
    assert "lingshu/modules.ini" not in names
    assert not any(name.startswith("framework/") for name in names)
