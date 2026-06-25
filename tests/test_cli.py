from framework.cli.main import add_version
from framework.cli.main import main
from framework.cli.main import make_module
from framework.cli.main import normalize_module_name
from framework.cli.main import normalize_version
from framework.cli.project import ProjectOptions
from framework.cli.project import render_project_files


def test_cli_add_version_scaffolds_mvc_layout(tmp_path):
    created = add_version("v2", root=tmp_path)

    assert tmp_path / "app" / "v2" in created
    assert (tmp_path / "app" / "v2" / "controller").exists()
    assert (tmp_path / "app" / "v2" / "model").exists()
    assert (tmp_path / "app" / "v2" / "view").exists()
    assert not (tmp_path / "app" / "v2" / "controller" / "index.py").exists()
    assert (tmp_path / "app" / "v2" / "language" / "zh-CN" / "ERROR").exists()
    assert (tmp_path / "app" / "v2" / "language" / "en-US" / "ERROR").exists()
    assert not (tmp_path / "app" / "v2" / "language" / "__init__.py").exists()
    assert not (tmp_path / "app" / "v2" / "language" / "zh-CN" / "ERROR" / "__init__.py").exists()


def test_cli_add_version_rejects_invalid_names():
    try:
        normalize_version("../v1")
    except ValueError as exc:
        assert "Version name" in str(exc)
    else:
        raise AssertionError("invalid version name should fail")


def test_cli_make_module_scaffolds_restful_module(tmp_path):
    controller = tmp_path / "app" / "v1" / "controller" / "demo.py"
    model = tmp_path / "app" / "v1" / "model" / "demo.py"
    view = tmp_path / "app" / "v1" / "view" / "demo" / "index.html"
    docs = tmp_path / "public" / "docs" / "v1" / "demo.md"
    route = tmp_path / "app" / "route.py"
    route.parent.mkdir(parents=True)
    route.write_text(
        "def get_blueprints(config=None):\n"
        "    from app.controller.health import bp as health_bp\n\n"
        "    blueprints = [health_bp]\n"
        "    return blueprints\n",
        encoding="utf-8",
    )

    created = make_module("v1", "demo", root=tmp_path)

    assert controller in created
    assert model.exists()
    assert view.exists()
    assert docs.exists()
    assert route in created

    controller_text = controller.read_text(encoding="utf-8")
    assert '@bp.get("/")' in controller_text
    assert '@bp.get("/<data_id>")' in controller_text
    assert '@bp.post("/")' in controller_text
    assert '@bp.put("/<data_id>")' in controller_text
    assert '@bp.delete("/<data_id>")' in controller_text
    assert "async def index(request):" in controller_text
    assert "async def info(request, data_id):" in controller_text
    assert "async def create(request):" in controller_text
    assert "async def update(request, data_id):" in controller_text
    assert "async def delete(request, data_id):" in controller_text
    assert '"/add"' not in controller_text
    assert '"/edit"' not in controller_text
    assert '"/del"' not in controller_text
    assert "@bp.patch" not in controller_text
    assert "partial_update" not in controller_text
    assert "raise_code(request, 990202" in controller_text
    assert "require_payload(request)" in controller_text
    assert 'request.app.ctx.logger.debug("demo.index' in controller_text
    assert 'request.app.ctx.logger.info("demo.create' in controller_text

    route_text = route.read_text(encoding="utf-8")
    assert "from app.v1.controller.demo import bp as v1_demo_bp" in route_text
    assert "blueprints.append(v1_demo_bp)" in route_text


def test_cli_make_module_registration_is_idempotent(tmp_path):
    route = tmp_path / "app" / "route.py"
    route.parent.mkdir(parents=True)
    route.write_text(
        "def get_blueprints(config=None):\n"
        "    from app.controller.health import bp as health_bp\n\n"
        "    blueprints = [health_bp]\n"
        "    return blueprints\n",
        encoding="utf-8",
    )

    make_module("v1", "demo", root=tmp_path)
    second_created = make_module("v1", "demo", root=tmp_path)

    route_text = route.read_text(encoding="utf-8")
    assert route_text.count("from app.v1.controller.demo import bp as v1_demo_bp") == 1
    assert route_text.count("blueprints.append(v1_demo_bp)") == 1
    assert route not in second_created


def test_cli_make_module_rejects_invalid_module_names():
    try:
        normalize_module_name("../demo")
    except ValueError as exc:
        assert "Module name" in str(exc)
    else:
        raise AssertionError("invalid module name should fail")


def test_cli_check_command_reports_project_contract(tmp_path, capsys):
    assert main(["check", "--root", str(tmp_path)]) == 1
    assert "Missing required file: run.py" in capsys.readouterr().out

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

    assert main(["check", "--root", str(tmp_path)]) == 0
    assert "Project check passed" in capsys.readouterr().out
