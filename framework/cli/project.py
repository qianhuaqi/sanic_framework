from __future__ import annotations

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
    "config/defaults.py",
    "app/language/modules.ini",
    "public/docs/index.md",
]


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
        "app/v1/controller",
        "app/v1/model",
        "app/v1/view",
        "app/v1/language/zh-CN/ERROR",
        "app/v1/language/en-US/ERROR",
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
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    return [f"Missing required file: {path}" for path in missing]
