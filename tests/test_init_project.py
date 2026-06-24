from framework.cli.project import ProjectOptions, render_project_files


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
    assert (tmp_path / "app" / "route.py").exists()
    assert (tmp_path / "app" / "controller" / "health.py").exists()
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
