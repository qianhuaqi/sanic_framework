import os
from pathlib import Path
import subprocess
import sys

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
    assert (tmp_path / "run.py").exists()
    assert (tmp_path / "app" / "bootstrap.py").exists()
    assert (tmp_path / "app" / "helper.py").exists()
    assert (tmp_path / "app" / "route.py").exists()
    assert (tmp_path / "app" / "controller" / "health.py").exists()
    assert (tmp_path / "config" / "defaults.py").exists()
    assert (tmp_path / "app" / "language" / "modules.ini").exists()
    assert not (tmp_path / "config" / "settings.py").exists()
    assert not (tmp_path / "app" / "language" / "__init__.py").exists()
    assert not (tmp_path / "app" / "language" / "zh-CN" / "ERROR" / "__init__.py").exists()
    assert not (tmp_path / "app" / "v1").exists()
    assert (tmp_path / "public" / "docs" / "index.md").exists()


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
        "    assert response.status == 503\n"
        "    assert response.json['code'] == 990201\n"
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
