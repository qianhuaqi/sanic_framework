import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from lingshu.cli.project import ProjectOptions, check_project, render_project_files


ROOT = Path(__file__).resolve().parents[1]


def test_initializer_renders_no_database_project(tmp_path):
    options = ProjectOptions(
        project_name="demo-api",
        app_name="demo_api",
        port=8100,
        databases=[],
        enable_auth=True,
        enable_signing=True,
        enable_i18n=True,
        enable_response_cache=True,
        include_example=False,
    )

    render_project_files(tmp_path, options)

    env_example = (tmp_path / ".env.example").read_text(encoding="utf-8")
    assert "PROJECT_NAME=demo-api" in env_example
    assert "PORT=8100" in env_example
    assert "MYSQL_ENABLED=false" in env_example
    assert "# [MYSQL]" in env_example
    assert "MYSQL_MASTER_HOST=localhost" not in env_example
    assert (tmp_path / "README.md").exists()
    assert (tmp_path / "pyproject.toml").exists()
    pyproject_text = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "demo-api"' in pyproject_text
    assert '"lingshu-framework>=0.2,<0.3"' in pyproject_text
    assert "[project.optional-dependencies]" in pyproject_text
    assert 'include = ["app*", "config*"]' in pyproject_text
    assert (tmp_path / "run.py").exists()
    run_text = (tmp_path / "run.py").read_text(encoding="utf-8")
    assert "from lingshu.runtime import run_app" in run_text
    assert 'python -m pip install -e ".[dev]"' in run_text
    assert "lingshu.system" not in run_text
    assert (tmp_path / "app" / "bootstrap.py").exists()
    assert (tmp_path / "app" / "helper.py").exists()
    assert (tmp_path / "app" / "route.py").exists()
    assert (tmp_path / "app" / "controller" / "health.py").exists()
    assert (tmp_path / "config" / "defaults.py").exists()
    assert (tmp_path / "app" / "language" / "modules.ini").exists()
    modules_text = (tmp_path / "app" / "language" / "modules.ini").read_text(encoding="utf-8")
    assert "\n110000-119999 = user" not in modules_text
    assert "# 110000-119999 = user" in modules_text
    assert not (tmp_path / "config" / "settings.py").exists()
    assert not (tmp_path / "app" / "language" / "__init__.py").exists()
    assert not (tmp_path / "app" / "language" / "zh-CN" / "ERROR" / "__init__.py").exists()
    assert not (tmp_path / "app" / "v1").exists()
    assert (tmp_path / "public" / "docs" / "index.md").exists()


def test_initialized_project_editable_install_in_fresh_venv_without_pythonpath(tmp_path):
    if os.getenv("LINGSHU_RUN_FRESH_VENV_SMOKE") != "1":
        pytest.skip("set LINGSHU_RUN_FRESH_VENV_SMOKE=1 to run the fresh-venv install smoke")

    project_dir = tmp_path / "generated"
    venv_dir = tmp_path / "venv"
    options = ProjectOptions(
        project_name="demo-api",
        app_name="demo_api",
        port=8100,
        databases=[],
        enable_auth=True,
        enable_signing=True,
        enable_i18n=True,
        enable_response_cache=True,
        include_example=False,
    )
    render_project_files(project_dir, options)
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    python = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    framework_install = subprocess.run(
        [str(python), "-m", "pip", "install", "-e", f"{ROOT}[dev]"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    assert framework_install.returncode == 0, framework_install.stderr
    install_result = subprocess.run(
        [str(python), "-m", "pip", "install", "-e", ".[dev]"],
        cwd=project_dir,
        env=env,
        text=True,
        capture_output=True,
    )
    assert install_result.returncode == 0, install_result.stderr

    smoke = textwrap.dedent(
        """
        import importlib
        module = importlib.import_module("run")
        assert module.app.name == "demo_api"
        print("generated project import ok")
        """
    )
    smoke_result = subprocess.run(
        [str(python), "-c", smoke],
        cwd=project_dir,
        env=env,
        text=True,
        capture_output=True,
    )
    assert smoke_result.returncode == 0, smoke_result.stderr
    assert "generated project import ok" in smoke_result.stdout


def test_initializer_renders_selected_databases(tmp_path):
    options = ProjectOptions(
        project_name="demo-api",
        app_name="demo_api",
        port=8100,
        databases=["mysql", "redis"],
        enable_auth=True,
        enable_signing=False,
        enable_i18n=True,
        enable_response_cache=False,
        include_example=True,
    )

    render_project_files(tmp_path, options)

    env_example = (tmp_path / ".env.example").read_text(encoding="utf-8")
    compose = (tmp_path / "docker-compose.yml").read_text(encoding="utf-8")
    assert "MYSQL_ENABLED=true" in env_example
    assert "REDIS_ENABLED=true" in env_example
    assert "MYSQL_MASTER_HOST=localhost" in env_example
    assert "MYSQL_SLAVES=" in env_example
    assert "REDIS_SENTINELS=" in env_example
    assert "CORS_ENABLED=false" in env_example
    assert "mongodb" not in compose


def test_initialized_project_can_create_app_and_serve_health(tmp_path):
    options = ProjectOptions(
        project_name="demo-api",
        app_name="demo_api",
        port=8100,
        databases=[],
        enable_auth=True,
        enable_signing=True,
        enable_i18n=True,
        enable_response_cache=True,
        include_example=False,
    )
    render_project_files(tmp_path, options)

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{tmp_path}{os.pathsep}{ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}"
    env["SANIC_ENV"] = "testing"
    script = (
        "import asyncio\n"
        "from lingshu.app import create_app\n"
        "async def main():\n"
        "    app = create_app()\n"
        "    _, response = await app.asgi_client.get('/health')\n"
        "    assert response.status == 200\n"
        "    assert response.json['data']['status'] == 'ok'\n"
        "asyncio.run(main())\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr


def test_initialized_project_make_module_is_registered(tmp_path):
    options = ProjectOptions(
        project_name="demo-api",
        app_name="demo_api",
        port=8100,
        databases=[],
        enable_auth=True,
        enable_signing=True,
        enable_i18n=True,
        enable_response_cache=True,
        include_example=False,
    )
    render_project_files(tmp_path, options)

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{tmp_path}{os.pathsep}{ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}"
    env["SANIC_ENV"] = "testing"
    add_result = subprocess.run(
        [sys.executable, "-m", "lingshu.cli.main", "add", "v1", "--root", str(tmp_path)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )
    assert add_result.returncode == 0, add_result.stderr

    make_result = subprocess.run(
        [sys.executable, "-m", "lingshu.cli.main", "make", "module", "v1", "demo", "--root", str(tmp_path)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )
    assert make_result.returncode == 0, make_result.stderr

    route_text = (tmp_path / "app" / "route.py").read_text(encoding="utf-8")
    assert "from app.v1.controller.demo import bp as v1_demo_bp" in route_text
    assert "blueprints.append(v1_demo_bp)" in route_text

    script = (
        "import asyncio\n"
        "from lingshu.app import create_app\n"
        "async def main():\n"
        "    app = create_app()\n"
        "    _, response = await app.asgi_client.get('/v1/demo')\n"
        "    assert response.status == 401\n"
        "    assert response.json['code'] == 990116\n"
        "asyncio.run(main())\n"
    )
    load_result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )
    assert load_result.returncode == 0, load_result.stderr


def test_check_project_requires_framework_project_contract(tmp_path):
    assert "Missing required file: run.py" in check_project(tmp_path)

    options = ProjectOptions(
        project_name="demo-api",
        app_name="demo_api",
        port=8100,
        databases=[],
        enable_auth=True,
        enable_signing=True,
        enable_i18n=True,
        enable_response_cache=True,
        include_example=False,
    )
    render_project_files(tmp_path, options)

    assert check_project(tmp_path) == []


def test_scaffolded_controller_default_is_auth_required(tmp_path):
    """Generated resource controllers must default to auth_required=True.

    The scaffold template must NOT include set_blueprint_policy with
    auth_required=False — that would leave every generated CRUD endpoint
    (including POST/PUT/PATCH/DELETE) anonymously open.
    """
    options = ProjectOptions(
        project_name="demo-api",
        app_name="demo_api",
        port=8100,
        databases=["mysql"],
        enable_auth=True,
        enable_signing=True,
        enable_i18n=True,
        enable_response_cache=True,
        include_example=True,
    )
    render_project_files(tmp_path, options)

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{tmp_path}{os.pathsep}{ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}"
    env["SANIC_ENV"] = "testing"
    add_result = subprocess.run(
        [sys.executable, "-m", "lingshu.cli.main", "add", "v1", "--root", str(tmp_path)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )
    assert add_result.returncode == 0, add_result.stderr

    make_result = subprocess.run(
        [sys.executable, "-m", "lingshu.cli.main", "make", "module", "v1", "orders", "--root", str(tmp_path)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )
    assert make_result.returncode == 0, make_result.stderr

    controller_text = (tmp_path / "app" / "v1" / "controller" / "orders.py").read_text(encoding="utf-8")
    assert "set_blueprint_policy" not in controller_text
    assert "auth_required=False" not in controller_text

    script = (
        "import asyncio\n"
        "from lingshu.app import create_app\n"
        "async def main():\n"
        "    app = create_app()\n"
        "    _, response = await app.asgi_client.get('/v1/orders')\n"
        "    assert response.status == 401\n"
        "    assert response.json['code'] == 990116\n"
        "asyncio.run(main())\n"
    )
    load_result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )
    assert load_result.returncode == 0, load_result.stderr
