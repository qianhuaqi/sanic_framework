from framework.cli.main import add_version
from framework.cli.main import main
from framework.cli.main import make_business_model
from framework.cli.main import make_model
from framework.cli.main import make_module
from framework.cli.main import normalize_module_name
from framework.cli.main import normalize_version
from framework.cli.project import ProjectOptions
from framework.cli.project import check_project
from framework.cli.project import render_project_files


def test_cli_add_version_scaffolds_mvc_layout(tmp_path):
    created = add_version("v2", root=tmp_path)

    assert tmp_path / "app" / "v2" in created
    assert (tmp_path / "app" / "v2" / "controller").exists()
    assert (tmp_path / "app" / "v2" / "model").exists()
    assert (tmp_path / "app" / "v2" / "model" / "table").exists()
    assert (tmp_path / "app" / "v2" / "model" / "business").exists()
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
    model = tmp_path / "app" / "v1" / "model" / "table" / "demo.py"
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
    assert '@bp.put("/<data_id>", name="update_put")' in controller_text
    assert '@bp.patch("/<data_id>", name="update_patch")' in controller_text
    assert '@bp.delete("/<data_id>")' in controller_text
    assert "async def index(request):" in controller_text
    assert "async def info(request, data_id):" in controller_text
    assert "async def create(request):" in controller_text
    assert "async def update(request, data_id):" in controller_text
    assert "async def delete(request, data_id):" in controller_text
    assert '"/add"' not in controller_text
    assert '"/edit"' not in controller_text
    assert '"/del"' not in controller_text
    assert "partial_update" not in controller_text
    assert "raise_code(request, 990202" in controller_text
    assert "default=" not in controller_text
    assert 'msg="' not in controller_text
    assert "errmsg=" not in controller_text
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


def test_cli_generators_do_not_overwrite_business_code(tmp_path):
    make_module("v1", "demo", root=tmp_path)
    controller = tmp_path / "app" / "v1" / "controller" / "demo.py"
    model = tmp_path / "app" / "v1" / "model" / "table" / "demo.py"
    business = tmp_path / "app" / "v1" / "model" / "business" / "permission_assign.py"
    controller.write_text("# user controller\n", encoding="utf-8")
    model.write_text("# user table model\n", encoding="utf-8")
    business.parent.mkdir(parents=True, exist_ok=True)
    business.write_text("# user business model\n", encoding="utf-8")

    assert make_module("v1", "demo", root=tmp_path) == []
    assert make_model("v1", "demo", root=tmp_path) == []
    assert make_business_model("v1", "permission_assign", root=tmp_path) == []

    assert controller.read_text(encoding="utf-8") == "# user controller\n"
    assert model.read_text(encoding="utf-8") == "# user table model\n"
    assert business.read_text(encoding="utf-8") == "# user business model\n"


def test_cli_make_module_rejects_invalid_module_names():
    try:
        normalize_module_name("../demo")
    except ValueError as exc:
        assert "Module name" in str(exc)
    else:
        raise AssertionError("invalid module name should fail")


def test_cli_make_model_scaffolds_physical_table_model(tmp_path):
    created = make_model("v1", "a_b_c", root=tmp_path)
    path = tmp_path / "app" / "v1" / "model" / "table" / "a_b_c.py"

    assert path in created
    text = path.read_text(encoding="utf-8")
    assert "class ABCModel(Model):" in text
    assert 'table_name = "a_b_c"' in text


def test_cli_make_model_treats_underscored_names_as_physical_tables(tmp_path):
    make_model("v1", "a", root=tmp_path)
    make_model("v1", "a_b", root=tmp_path)
    make_model("v1", "a_b_c", root=tmp_path)

    assert (tmp_path / "app" / "v1" / "model" / "table" / "a.py").exists()
    assert (tmp_path / "app" / "v1" / "model" / "table" / "a_b.py").exists()
    assert (tmp_path / "app" / "v1" / "model" / "table" / "a_b_c.py").exists()


def test_cli_make_business_model_scaffolds_business_model(tmp_path):
    created = make_business_model("v1", "permission_assign", root=tmp_path)
    path = tmp_path / "app" / "v1" / "model" / "business" / "permission_assign.py"

    assert path in created
    text = path.read_text(encoding="utf-8")
    assert "class PermissionAssignBusinessModel(BusinessModel):" in text
    assert "table_name" not in text


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


def test_check_project_detects_illegal_controller_contract(tmp_path):
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
    add_version("v1", root=tmp_path)
    controller = tmp_path / "app" / "v1" / "controller" / "demo.py"
    controller.write_text(
        "from sanic import Blueprint\n"
        "bp = Blueprint('v1_demo')\n"
        "@bp.get('/')\n"
        "async def index(request):\n"
        "    return {}\n"
        "@bp.patch('/<data_id>')\n"
        "async def partial_update(request, data_id):\n"
        "    raise_code(request, 991111, default='bad')\n",
        encoding="utf-8",
    )

    issues = check_project(tmp_path)

    assert any("app/v1/controller/demo.py" in issue and "partial_update" in issue for issue in issues)
    assert any("app/v1/controller/demo.py" in issue and "hard coded" in issue for issue in issues)
    assert any("app/v1/controller/demo.py" in issue and "update" in issue and "PUT" in issue for issue in issues)


def test_check_project_detects_illegal_table_model_contract(tmp_path):
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
    add_version("v1", root=tmp_path)
    path = tmp_path / "app" / "v1" / "model" / "table" / "demo.py"
    path.write_text("class DemoModel:\n    pass\n", encoding="utf-8")

    issues = check_project(tmp_path)

    assert any("app/v1/model/table/demo.py" in issue and "inherit Model" in issue for issue in issues)
    assert any("app/v1/model/table/demo.py" in issue and "table_name" in issue for issue in issues)


def test_check_project_detects_illegal_business_model_contract(tmp_path):
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
    add_version("v1", root=tmp_path)
    path = tmp_path / "app" / "v1" / "model" / "business" / "permission_assign.py"
    path.write_text(
        "from framework.model.business import BusinessModel\n"
        "class PermissionAssignModel(BusinessModel):\n"
        "    table_name = 'permission_assign'\n",
        encoding="utf-8",
    )

    issues = check_project(tmp_path)

    assert any("app/v1/model/business/permission_assign.py" in issue and "BusinessModel" in issue for issue in issues)
    assert any("app/v1/model/business/permission_assign.py" in issue and "must not declare table_name" in issue for issue in issues)
