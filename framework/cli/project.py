from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


SCAFFOLD_DIR = Path(__file__).resolve().parents[1] / "scaffold"
REQUIRED_FILES = [
    "run.py",
    ".env.example",
    "README.md",
    "app/bootstrap.py",
    "app/route.py",
    "app/common.py",
    "app/helper.py",
    "app/event.py",
    "app/controller",
    "config/defaults.py",
    "app/language/modules.ini",
    "public/docs/index.md",
]
CONTROLLER_HANDLERS = {"index", "info", "create", "update", "delete"}
HTTP_DECORATORS = {"get", "post", "put", "patch", "delete"}


@dataclass(frozen=True)
class ProjectOptions:
    project_name: str
    app_name: str
    port: int
    databases: list[str]
    enable_auth: bool
    enable_signing: bool
    enable_i18n: bool
    enable_response_cache: bool
    include_example: bool


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(SCAFFOLD_DIR)),
        autoescape=False,
        keep_trailing_newline=True,
    )


def render_scaffold_template(template_name: str, **context) -> str:
    return _environment().get_template(template_name).render(**context)


def render_project_files(target_dir: Path, options: ProjectOptions):
    target_dir.mkdir(parents=True, exist_ok=True)
    env = _environment()
    context = options.__dict__

    files = {
        ".env.example": "env.example.j2",
        "README.md": "README.md.j2",
        "docker-compose.yml": "docker-compose.yml.j2",
    }
    for output_name, template_name in files.items():
        rendered = env.get_template(template_name).render(**context)
        (target_dir / output_name).write_text(rendered, encoding="utf-8")

    _render_project_skeleton(target_dir, options)


def _write_if_missing(path: Path, content: str = ""):
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _render_project_skeleton(target_dir: Path, options: ProjectOptions):
    directories = (
        "app/controller",
        "config",
        "app/language/zh-CN/ERROR",
        "app/language/en-US/ERROR",
        "public/docs",
    )
    for directory in directories:
        dir_path = target_dir / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        if "public" not in directory:
            current = dir_path
            while current != target_dir:
                if current.name not in {"public", "docs", "language", "zh-CN", "en-US", "ERROR"}:
                    _write_if_missing(current / "__init__.py", "__all__ = []\n")
                current = current.parent

    _write_if_missing(
        target_dir / "run.py",
        "from framework.app import create_app\n\n\n"
        "app = create_app()\n\n\n"
        "if __name__ == \"__main__\":\n"
        "    config = app.ctx.config\n"
        "    app.run(host=config.host, port=config.port, debug=config.debug, workers=config.workers)\n",
    )
    _write_if_missing(
        target_dir / "app" / "bootstrap.py",
        "def get_extension_modules():\n"
        "    from framework.extensions import mongo, mysql, redis\n\n"
        "    return [mysql, redis, mongo]\n\n\n"
        "def get_feature_blueprints(config=None):\n"
        "    from app.route import get_blueprints\n\n"
        "    return get_blueprints(config)\n",
    )
    _write_if_missing(
        target_dir / "app" / "route.py",
        "import os\n\n\n"
        "def _is_dev_or_test(config=None):\n"
        "    environment = os.getenv(\"SANIC_ENV\", \"development\").lower()\n"
        "    enabled = environment in {\"development\", \"dev\", \"test\", \"testing\"}\n"
        "    if config is not None:\n"
        "        enabled = enabled or bool(getattr(config, \"debug\", False))\n"
        "    return enabled\n\n\n"
        "def get_blueprints(config=None):\n"
        "    from app.controller.health import bp as health_bp\n\n"
        "    blueprints = [health_bp]\n"
        "    return blueprints\n",
    )
    _write_if_missing(
        target_dir / "app" / "controller" / "health.py",
        "from sanic import Blueprint\n\n"
        "from framework.response import json_response\n"
        "from framework.router import RoutePolicy, set_blueprint_policy\n\n\n"
        "bp = Blueprint(\"health\")\n"
        "set_blueprint_policy(bp, RoutePolicy(auth_required=False, signing_required=False, maintenance_check=False))\n\n\n"
        "@bp.get(\"/\")\n"
        "async def root(request):\n"
        "    return json_response({\"status\": \"ok\"})\n\n\n"
        "@bp.get(\"/health\")\n"
        "async def health(request):\n"
        "    return json_response({\"status\": \"ok\"})\n",
    )
    _write_if_missing(target_dir / "app" / "common.py", "__all__ = []\n")
    _write_if_missing(
        target_dir / "app" / "helper.py",
        "def mask_mobile(mobile: str) -> str:\n"
        "    if not mobile or len(mobile) < 7:\n"
        "        return mobile\n"
        "    return f\"{mobile[:3]}****{mobile[-4:]}\"\n",
    )
    _write_if_missing(target_dir / "app" / "event.py", "__all__ = []\n")
    _write_if_missing(
        target_dir / "config" / "defaults.py",
        f'APP_NAME = "{options.app_name}"\n'
        f'PROJECT_NAME = "{options.project_name}"\n'
        f"PORT = {options.port}\n"
        'LANGUAGE = "zh-CN"\n'
        'LOCALE_DIR = "app/language"\n'
        "CORS_ENABLED = False\n"
        "LOG_TO_FILE = False\n"
        'LOG_LEVEL = "INFO"\n'
        'LOG_PATH = "runtime/logs"\n'
        'LOG_FILE = "app.log"\n'
        'LOG_FORMATTER = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"\n'
        "LOG_MAX_BYTES = 10485760\n"
        "LOG_BACKUP_COUNT = 7\n",
    )
    _write_if_missing(target_dir / "public" / "docs" / "index.md", f"# {options.project_name} API Docs\n")
    _write_if_missing(
        target_dir / "app" / "language" / "modules.ini",
        "[Modules]\n"
        "100000-109999 = language\n"
        "110000-119999 = user\n"
        "990000-990099 = system\n"
        "990100-990199 = auth\n"
        "990200-990299 = db\n"
        "991100-991199 = param\n",
    )


def check_project(root: Path) -> list[str]:
    issues = [f"Missing required file: {path}" for path in REQUIRED_FILES if not (root / path).exists()]
    issues.extend(_check_controllers(root))
    issues.extend(_check_table_models(root))
    issues.extend(_check_business_models(root))
    return issues


def _relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _parse_python(root: Path, path: Path) -> tuple[ast.Module | None, list[str]]:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path)), []
    except SyntaxError as exc:
        return None, [f"{_relative(root, path)}: invalid Python syntax: {exc.msg}"]


def _base_name(base: ast.expr) -> str:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    if isinstance(base, ast.Subscript):
        return _base_name(base.value)
    return ""


def _inherits(class_node: ast.ClassDef, base_name: str) -> bool:
    return any(_base_name(base) == base_name for base in class_node.bases)


def _class_has_assignment(class_node: ast.ClassDef, name: str) -> bool:
    for node in class_node.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return True
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return True
    return False


def _route_decorators(function_node: ast.AsyncFunctionDef | ast.FunctionDef) -> list[tuple[str, str]]:
    routes: list[tuple[str, str]] = []
    for decorator in function_node.decorator_list:
        call = decorator if isinstance(decorator, ast.Call) else None
        func = call.func if call is not None else decorator
        if not isinstance(func, ast.Attribute) or func.attr not in HTTP_DECORATORS:
            continue
        route = ""
        if call is not None and call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
            route = call.args[0].value
        routes.append((func.attr, route))
    return routes


def _has_hard_coded_error_message(function_node: ast.AST) -> bool:
    for node in ast.walk(function_node):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg in {"default", "msg", "errmsg"} and isinstance(keyword.value, ast.Constant):
                if isinstance(keyword.value.value, str) and keyword.value.value:
                    return True
    return False


def _version_paths(root: Path) -> list[Path]:
    app_root = root / "app"
    if not app_root.exists():
        return []
    return [path for path in app_root.iterdir() if path.is_dir() and path.name.startswith("v")]


def _check_controllers(root: Path) -> list[str]:
    issues: list[str] = []
    for version_path in _version_paths(root):
        controller_root = version_path / "controller"
        if not controller_root.exists():
            continue
        for path in sorted(controller_root.glob("*.py")):
            if path.name == "__init__.py":
                continue
            module, parse_issues = _parse_python(root, path)
            issues.extend(parse_issues)
            if module is None:
                continue
            functions = [
                node
                for node in module.body
                if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and not node.name.startswith("_")
            ]
            names = {node.name for node in functions}
            extra = sorted(names - CONTROLLER_HANDLERS)
            missing = sorted(CONTROLLER_HANDLERS - names)
            if extra:
                issues.append(f"{_relative(root, path)}: standard controller has unsupported handlers: {', '.join(extra)}")
            if missing:
                issues.append(f"{_relative(root, path)}: standard controller is missing handlers: {', '.join(missing)}")
            if "partial_update" in names:
                issues.append(f"{_relative(root, path)}: partial_update is forbidden")
            for function_node in functions:
                if _has_hard_coded_error_message(function_node):
                    issues.append(f"{_relative(root, path)}: hard coded error messages are forbidden")
            update = next((node for node in functions if node.name == "update"), None)
            update_routes = set(_route_decorators(update)) if update is not None else set()
            if ("put", "/<data_id>") not in update_routes or ("patch", "/<data_id>") not in update_routes:
                issues.append(f"{_relative(root, path)}: update must bind both PUT and PATCH on /<data_id>")
    return issues


def _check_table_models(root: Path) -> list[str]:
    issues: list[str] = []
    for version_path in _version_paths(root):
        table_root = version_path / "model" / "table"
        if not table_root.exists():
            continue
        for path in sorted(table_root.glob("*.py")):
            if path.name == "__init__.py":
                continue
            module, parse_issues = _parse_python(root, path)
            issues.extend(parse_issues)
            if module is None:
                continue
            classes = [node for node in module.body if isinstance(node, ast.ClassDef)]
            model_classes = [node for node in classes if _inherits(node, "Model")]
            if len(model_classes) != 1:
                issues.append(f"{_relative(root, path)}: table model files must define exactly one class that inherit Model")
            candidate = model_classes[0] if model_classes else classes[0] if classes else None
            if candidate is None or not _class_has_assignment(candidate, "table_name"):
                issues.append(f"{_relative(root, path)}: table model must declare table_name")
    return issues


def _check_business_models(root: Path) -> list[str]:
    issues: list[str] = []
    for version_path in _version_paths(root):
        business_root = version_path / "model" / "business"
        if not business_root.exists():
            continue
        for path in sorted(business_root.glob("*.py")):
            if path.name == "__init__.py":
                continue
            module, parse_issues = _parse_python(root, path)
            issues.extend(parse_issues)
            if module is None:
                continue
            classes = [node for node in module.body if isinstance(node, ast.ClassDef)]
            business_classes = [node for node in classes if _inherits(node, "BusinessModel")]
            if len(business_classes) != 1:
                issues.append(f"{_relative(root, path)}: business model files must define exactly one class that inherit BusinessModel")
                continue
            class_node = business_classes[0]
            if not class_node.name.endswith("BusinessModel"):
                issues.append(f"{_relative(root, path)}: business model class name must end with BusinessModel")
            if _class_has_assignment(class_node, "table_name"):
                issues.append(f"{_relative(root, path)}: BusinessModel must not declare table_name")
    return issues
