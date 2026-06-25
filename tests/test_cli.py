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


def _render_project(tmp_path):
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
    return options


def _resource_controller(extra: str = "") -> str:
    return (
        'from sanic import Blueprint\n'
        'bp = Blueprint("v1_demo")\n'
        'CONTROLLER_KIND = "resource"\n'
        '@bp.get("/")\n'
        'async def index(request):\n'
        '    return {}\n'
        '@bp.get("/<data_id>")\n'
        'async def info(request, data_id):\n'
        '    return {}\n'
        '@bp.post("/")\n'
        'async def create(request):\n'
        '    return {}\n'
        '@bp.put("/<data_id>")\n'
        '@bp.patch("/<data_id>")\n'
        'async def update(request, data_id):\n'
        '    return {}\n'
        '@bp.delete("/<data_id>")\n'
        'async def delete(request, data_id):\n'
        '    return {}\n'
        f'{extra}'
    )


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
    for value in ("1", "admin", "v", "v_", "../v1", "v1/../../x", "v1-admin/../../x"):
        try:
            normalize_version(value)
        except ValueError as exc:
            assert "Version name" in str(exc)
        else:
            raise AssertionError(f"invalid version name should fail: {value}")


def test_cli_version_accepts_supported_names():
    assert normalize_version("v1") == "v1"
    assert normalize_version("v2") == "v2"
    assert normalize_version("v1_admin") == "v1_admin"
    assert normalize_version("v2_partner") == "v2_partner"


def test_cli_make_requires_explicit_add_version(tmp_path, capsys):
    _render_project(tmp_path)

    assert main(["make", "module", "v1", "demo", "--root", str(tmp_path)]) == 1
    assert "Version 'v1' does not exist. Run: sanic-framework add v1" in capsys.readouterr().err
    assert not (tmp_path / "app" / "v1").exists()

    assert main(["make", "model", "v1", "user", "--root", str(tmp_path)]) == 1
    assert "Version 'v1' does not exist. Run: sanic-framework add v1" in capsys.readouterr().err
    assert not (tmp_path / "app" / "v1").exists()

    assert main(["make", "business-model", "v1", "permission_assign", "--root", str(tmp_path)]) == 1
    assert "Version 'v1' does not exist. Run: sanic-framework add v1" in capsys.readouterr().err
    assert not (tmp_path / "app" / "v1").exists()


def test_cli_make_succeeds_after_add_version(tmp_path):
    _render_project(tmp_path)
    add_version("v1", root=tmp_path)

    assert main(["make", "module", "v1", "demo", "--root", str(tmp_path)]) == 0
    assert main(["make", "model", "v1", "user", "--root", str(tmp_path)]) == 0
    assert main(["make", "business-model", "v1", "permission_assign", "--root", str(tmp_path)]) == 0

    assert (tmp_path / "app" / "v1" / "controller" / "demo.py").exists()
    assert (tmp_path / "app" / "v1" / "model" / "table" / "user.py").exists()
    assert (tmp_path / "app" / "v1" / "model" / "business" / "permission_assign.py").exists()


def test_cli_make_module_scaffolds_restful_module(tmp_path):
    add_version("v1", root=tmp_path)
    controller = tmp_path / "app" / "v1" / "controller" / "demo.py"
    model = tmp_path / "app" / "v1" / "model" / "table" / "demo.py"
    view = tmp_path / "app" / "v1" / "view" / "demo" / "index.html"
    docs = tmp_path / "public" / "docs" / "v1" / "demo.md"
    route = tmp_path / "app" / "route.py"
    route.parent.mkdir(parents=True, exist_ok=True)
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
    assert 'CONTROLLER_KIND = "resource"' in controller_text
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
    add_version("v1", root=tmp_path)
    route = tmp_path / "app" / "route.py"
    route.parent.mkdir(parents=True, exist_ok=True)
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
    add_version("v1", root=tmp_path)
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
    add_version("v1", root=tmp_path)
    created = make_model("v1", "a_b_c", root=tmp_path)
    path = tmp_path / "app" / "v1" / "model" / "table" / "a_b_c.py"

    assert path in created
    text = path.read_text(encoding="utf-8")
    assert "class ABCModel(Model):" in text
    assert 'table_name = "a_b_c"' in text


def test_cli_make_model_treats_underscored_names_as_physical_tables(tmp_path):
    add_version("v1", root=tmp_path)
    make_model("v1", "a", root=tmp_path)
    make_model("v1", "a_b", root=tmp_path)
    make_model("v1", "a_b_c", root=tmp_path)

    assert (tmp_path / "app" / "v1" / "model" / "table" / "a.py").exists()
    assert (tmp_path / "app" / "v1" / "model" / "table" / "a_b.py").exists()
    assert (tmp_path / "app" / "v1" / "model" / "table" / "a_b_c.py").exists()


def test_cli_make_business_model_scaffolds_business_model(tmp_path):
    add_version("v1", root=tmp_path)
    created = make_business_model("v1", "permission_assign", root=tmp_path)
    path = tmp_path / "app" / "v1" / "model" / "business" / "permission_assign.py"

    assert path in created
    text = path.read_text(encoding="utf-8")
    assert "class PermissionAssignBusinessModel(BusinessModel):" in text
    assert "table_name" not in text
    assert "get_detail" not in text
    assert "return" not in text


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
    _render_project(tmp_path)
    add_version("v1", root=tmp_path)
    controller = tmp_path / "app" / "v1" / "controller" / "demo.py"
    controller.write_text(
        "from sanic import Blueprint\n"
        "bp = Blueprint('v1_demo')\n"
        "CONTROLLER_KIND = 'resource'\n"
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


def test_check_project_allows_action_controller_and_flags_action_errors(tmp_path):
    _render_project(tmp_path)
    add_version("v1", root=tmp_path)
    path = tmp_path / "app" / "v1" / "controller" / "login.py"
    path.write_text(
        "from sanic import Blueprint\n"
        "bp = Blueprint('v1_login')\n"
        "CONTROLLER_KIND = 'action'\n"
        "@bp.post('/')\n"
        "async def login(request):\n"
        "    request.app.ctx.logger.info('login attempt')\n"
        "    return {'status': 'ok'}\n",
        encoding="utf-8",
    )

    assert check_project(tmp_path) == []

    path.write_text(
        "from sanic import Blueprint\n"
        "bp = Blueprint('v1_login')\n"
        "CONTROLLER_KIND = 'action'\n"
        "@bp.post('/')\n"
        "async def login(request):\n"
        "    raise_code(request, 991111, default='bad')\n",
        encoding="utf-8",
    )

    issues = check_project(tmp_path)

    assert any("app/v1/controller/login.py" in issue and "hard coded" in issue for issue in issues)


def test_check_project_resource_controller_route_contract(tmp_path):
    _render_project(tmp_path)
    add_version("v1", root=tmp_path)
    path = tmp_path / "app" / "v1" / "controller" / "demo.py"

    broken_cases = {
        "index route": _resource_controller().replace('@bp.get("/")\nasync def index', '@bp.post("/")\nasync def index'),
        "info route": _resource_controller().replace('@bp.get("/<data_id>")\nasync def info', '@bp.delete("/<data_id>")\nasync def info'),
        "create route": _resource_controller().replace('@bp.post("/")\nasync def create', '@bp.get("/")\nasync def create'),
        "delete route": _resource_controller().replace('@bp.delete("/<data_id>")\nasync def delete', '@bp.patch("/<data_id>")\nasync def delete'),
        "missing PUT": _resource_controller().replace('@bp.put("/<data_id>")\n', ""),
        "missing PATCH": _resource_controller().replace('@bp.patch("/<data_id>")\n', ""),
        "extra handler": _resource_controller("@bp.get('/extra')\nasync def export(request):\n    return {}\n"),
        "duplicate handler": _resource_controller("@bp.get('/again')\nasync def index(request):\n    return {}\n"),
    }

    for label, source in broken_cases.items():
        path.write_text(source, encoding="utf-8")
        issues = check_project(tmp_path)
        assert any("app/v1/controller/demo.py" in issue for issue in issues), label


def test_check_project_detects_illegal_table_model_contract(tmp_path):
    _render_project(tmp_path)
    add_version("v1", root=tmp_path)
    path = tmp_path / "app" / "v1" / "model" / "table" / "demo.py"
    path.write_text("class DemoModel:\n    pass\n", encoding="utf-8")

    issues = check_project(tmp_path)

    assert any("app/v1/model/table/demo.py" in issue and "inherit Model" in issue for issue in issues)
    assert any("app/v1/model/table/demo.py" in issue and "table_name" in issue for issue in issues)


def test_check_project_detects_illegal_business_model_contract(tmp_path):
    _render_project(tmp_path)
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


def test_check_project_detects_missing_version_directories(tmp_path):
    _render_project(tmp_path)
    version_root = tmp_path / "app" / "v1"
    version_root.mkdir(parents=True)

    issues = check_project(tmp_path)

    assert any("app/v1/model/table" in issue and "required directory is missing" in issue for issue in issues)
    assert any("app/v1/model/business" in issue and "required directory is missing" in issue for issue in issues)


def test_check_project_detects_model_contract_details_and_wrong_directories(tmp_path):
    _render_project(tmp_path)
    add_version("v1", root=tmp_path)
    table_path = tmp_path / "app" / "v1" / "model" / "table" / "user.py"
    table_path.write_text(
        "from framework.model.model import Model\n"
        "class UserModel(Model):\n"
        "    table_name = ''\n",
        encoding="utf-8",
    )
    mismatch_path = tmp_path / "app" / "v1" / "model" / "table" / "account.py"
    mismatch_path.write_text(
        "from framework.model.model import Model\n"
        "class AccountModel(Model):\n"
        "    table_name = 'user_account'\n",
        encoding="utf-8",
    )
    wrong_table_path = tmp_path / "app" / "v1" / "model" / "table" / "workflow.py"
    wrong_table_path.write_text(
        "from framework.model.business import BusinessModel\n"
        "class WorkflowBusinessModel(BusinessModel):\n"
        "    pass\n",
        encoding="utf-8",
    )
    wrong_business_path = tmp_path / "app" / "v1" / "model" / "business" / "user.py"
    wrong_business_path.write_text(
        "from framework.model.model import Model\n"
        "class UserModel(Model):\n"
        "    table_name = 'user'\n",
        encoding="utf-8",
    )

    issues = check_project(tmp_path)

    assert any("app/v1/model/table/user.py" in issue and "non-empty string" in issue for issue in issues)
    assert any("app/v1/model/table/account.py" in issue and "must match table_name" in issue for issue in issues)
    assert any("app/v1/model/table/workflow.py" in issue and "BusinessModel" in issue for issue in issues)
    assert any("app/v1/model/business/user.py" in issue and "must not inherit Model" in issue for issue in issues)


def test_check_project_detects_hard_coded_errors_in_business_code(tmp_path):
    _render_project(tmp_path)
    add_version("v1", root=tmp_path)
    controller = tmp_path / "app" / "v1" / "controller" / "demo.py"
    controller.write_text(_resource_controller(), encoding="utf-8")
    business = tmp_path / "app" / "v1" / "model" / "business" / "permission_assign.py"
    business.write_text(
        "from framework.model.business import BusinessModel\n"
        "class PermissionAssignBusinessModel(BusinessModel):\n"
        "    async def assign(self):\n"
        "        self.logger.info('normal log text')\n"
        "        return {'message': 'normal return data'}\n"
        "    async def fail(self):\n"
        "        raise_code(self.request, 991111, default='bad')\n",
        encoding="utf-8",
    )
    table = tmp_path / "app" / "v1" / "model" / "table" / "user.py"
    table.write_text(
        "from framework.model.model import Model\n"
        "class UserModel(Model):\n"
        "    table_name = 'user'\n"
        "    async def fail(self):\n"
        "        APIException(code=991111, msg='bad')\n",
        encoding="utf-8",
    )
    helper = tmp_path / "app" / "helper.py"
    helper.write_text("def fail():\n    APIException(code=991111, errmsg='bad')\n", encoding="utf-8")

    issues = check_project(tmp_path)

    assert any("app/v1/model/business/permission_assign.py" in issue and "hard coded" in issue for issue in issues)
    assert any("app/v1/model/table/user.py" in issue and "hard coded" in issue for issue in issues)
    assert any("app/helper.py" in issue and "legacy error keyword" in issue for issue in issues)
    assert not any("normal log text" in issue or "normal return data" in issue for issue in issues)


def test_check_project_detects_legacy_error_keywords_in_all_app_calls(tmp_path):
    _render_project(tmp_path)
    add_version("v1", root=tmp_path)
    legacy_code = "err" + "code"
    legacy_message = "err" + "msg"
    files = {
        "app/controller/health.py": (
            "from framework.response import json_response\n"
            "async def health(request):\n"
            f"    return json_response({legacy_code}=1)\n"
        ),
        "app/v1/controller/demo.py": _resource_controller(
            "async def _bad(request):\n"
            f"    return json_response({legacy_message}='bad')\n"
        ),
        "app/v1/model/business/permission_assign.py": (
            "from framework.model.business import BusinessModel\n"
            "class PermissionAssignBusinessModel(BusinessModel):\n"
            "    async def fail(self):\n"
            f"        return json_response({legacy_code}=1)\n"
        ),
        "app/v1/model/table/user.py": (
            "from framework.model.model import Model\n"
            "class UserModel(Model):\n"
            "    table_name = 'user'\n"
            "    async def fail(self):\n"
            f"        return json_response({legacy_message}='bad')\n"
        ),
        "app/helper.py": (
            "def fail():\n"
            f"    return json_response({legacy_code}=1)\n"
        ),
        "app/event.py": (
            "def fail():\n"
            f"    return json_response({legacy_message}='bad')\n"
        ),
    }
    for relative, source in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    issues = check_project(tmp_path)

    for relative in files:
        assert any(relative in issue and "legacy error keyword" in issue for issue in issues), relative


def test_check_project_does_not_flag_plain_legacy_named_variables(tmp_path):
    _render_project(tmp_path)
    path = tmp_path / "app" / "future.py"
    path.write_text(
        "def describe():\n"
        "    errcode = 'sample only'\n"
        "    errmsg = 'sample only'\n"
        "    return {'errcode': errcode, 'errmsg': errmsg}\n",
        encoding="utf-8",
    )

    issues = check_project(tmp_path)

    assert not any("app/future.py" in issue for issue in issues)
