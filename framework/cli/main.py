from __future__ import annotations

import argparse
import re
from pathlib import Path

from framework.cli.project import ProjectOptions
from framework.cli.project import check_project
from framework.cli.project import render_project_files


VERSION_PATTERN = re.compile(r"^v[0-9][A-Za-z0-9_]*$")
MODULE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def _write_if_missing(path: Path, content: str = "") -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _touch_init(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    _write_if_missing(directory / "__init__.py", "__all__ = []\n")


def normalize_version(version: str) -> str:
    normalized = version.strip().replace("-", "_")
    if not VERSION_PATTERN.match(normalized):
        raise ValueError("Version name must look like v1, v2, or v1_admin")
    return normalized


def normalize_module_name(module: str) -> str:
    normalized = module.strip().replace("-", "_").lower()
    if not MODULE_PATTERN.match(normalized):
        raise ValueError("Module name must use snake_case, such as demo or user_profile")
    return normalized


def _pascal_case(value: str) -> str:
    return "".join(part.capitalize() for part in value.split("_") if part)


def add_version(version: str, root: str | Path = ".") -> list[Path]:
    root_path = Path(root).resolve()
    version_name = normalize_version(version)
    app_root = root_path / "app"
    version_root = app_root / version_name
    created: list[Path] = []

    for directory in (
        version_root,
        version_root / "controller",
        version_root / "model",
        version_root / "view",
        version_root / "language",
        version_root / "language" / "zh-CN",
        version_root / "language" / "zh-CN" / "ERROR",
        version_root / "language" / "en-US",
        version_root / "language" / "en-US" / "ERROR",
    ):
        existed = directory.exists()
        _touch_init(directory)
        if not existed:
            created.append(directory)

    return created


def make_module(version: str, module: str, root: str | Path = ".") -> list[Path]:
    root_path = Path(root).resolve()
    version_name = normalize_version(version)
    module_name = normalize_module_name(module)
    model_class = f"{_pascal_case(module_name)}Model"
    version_root = root_path / "app" / version_name
    docs_root = root_path / "public" / "docs" / version_name
    created = add_version(version_name, root_path)

    view_dir = version_root / "view" / module_name
    docs_root.mkdir(parents=True, exist_ok=True)
    _touch_init(view_dir)

    controller = f'''from __future__ import annotations

from sanic import Blueprint

from app.{version_name}.model.{module_name} import {model_class}
from framework.exception import APIException
from framework.response import json_response


bp = Blueprint("{version_name}_{module_name}", url_prefix="/{version_name}/{module_name}")


def _get_mysql(request):
    db = getattr(request.app.ctx, "mysql", None)
    if db is None:
        raise APIException(errcode=503000, errmsg="mysql is not enabled", status_code=503)
    return db


def _get_json_payload(request):
    payload = request.json or {{}}
    if not isinstance(payload, dict):
        raise APIException(errcode=400000, errmsg="invalid json body", status_code=400)
    return payload


@bp.get("/")
async def index(request):
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 10))
    use_master = request.args.get("use_master", "").lower() in {{"1", "true", "yes", "on"}}
    result = await {model_class}(request).get_pagination(page=page, size=size, use_master=use_master)
    return json_response(result)


@bp.get("/<data_id>")
async def info(request, data_id):
    use_cache = request.args.get("use_cache", "1").lower() not in {{"0", "false", "no", "off"}}
    use_master = request.args.get("use_master", "").lower() in {{"1", "true", "yes", "on"}}
    item = await {model_class}(request).get_one(data_id, use_master=use_master, use_cache=use_cache)
    if item is None:
        raise APIException(errcode=404000, errmsg="{module_name} row not found", status_code=404)
    return json_response(item)


@bp.post("/")
async def create(request):
    payload = _get_json_payload(request)
    data_id = await {model_class}(request).insert(**payload)
    return json_response({{"id": data_id, "payload": payload}}, status=201)


@bp.put("/<data_id>")
async def update(request, data_id):
    payload = _get_json_payload(request)
    if not payload:
        raise APIException(errcode=400002, errmsg="update payload is empty", status_code=400)
    result = await {model_class}(request).update(data_id, **payload)
    return json_response({{"id": data_id, "updated": result}})


@bp.patch("/<data_id>")
async def partial_update(request, data_id):
    payload = _get_json_payload(request)
    if not payload:
        raise APIException(errcode=400002, errmsg="update payload is empty", status_code=400)
    result = await {model_class}(request).update(data_id, **payload)
    return json_response({{"id": data_id, "updated": result}})


@bp.delete("/<data_id>")
async def delete(request, data_id):
    result = await {model_class}(request).delete(data_id)
    return json_response({{"id": data_id, "deleted": result}})
'''
    model = f'''from framework.model.model import Model


class {model_class}(Model):
    table_name = "{module_name}"
    read_source = "auto"
    cache_enabled = True
'''
    view = f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{version_name}/{module_name}</title>
</head>
<body></body>
</html>
'''
    docs = f'''# {version_name}/{module_name}

RESTful routes:

- `GET /{version_name}/{module_name}`
- `GET /{version_name}/{module_name}/<id>`
- `POST /{version_name}/{module_name}`
- `PUT /{version_name}/{module_name}/<id>`
- `PATCH /{version_name}/{module_name}/<id>`
- `DELETE /{version_name}/{module_name}/<id>`
'''
    files = {
        version_root / "controller" / f"{module_name}.py": controller,
        version_root / "model" / f"{module_name}.py": model,
        view_dir / "index.html": view,
        docs_root / f"{module_name}.md": docs,
    }
    for path, content in files.items():
        if _write_if_missing(path, content):
            created.append(path)
    return created


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sanic-framework")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Render project files into a target directory")
    init_parser.add_argument("project_name", help="Project name, for example demo-api")
    init_parser.add_argument("--root", default=".", help="Target project directory")
    init_parser.add_argument("--app-name", default=None, help="Python app name; defaults to project name normalized")
    init_parser.add_argument("--port", type=int, default=8000, help="Application port")
    init_parser.add_argument("--databases", default="", help="Comma-separated databases: mysql,redis,mongo")
    init_parser.add_argument("--disable-auth", action="store_true")
    init_parser.add_argument("--disable-signing", action="store_true")
    init_parser.add_argument("--disable-i18n", action="store_true")
    init_parser.add_argument("--disable-response-cache", action="store_true")

    add_parser = subparsers.add_parser("add", help="Create a versioned MVC app, such as v1 or v2")
    add_parser.add_argument("version", help="Version name, for example v1")
    add_parser.add_argument("--root", default=".", help="Project root directory")

    make_parser = subparsers.add_parser("make", help="Generate project code")
    make_subparsers = make_parser.add_subparsers(dest="make_command", required=True)
    module_parser = make_subparsers.add_parser("module", help="Create a RESTful MVC module")
    module_parser.add_argument("version", help="Version name, for example v1")
    module_parser.add_argument("module", help="Module name, for example demo")
    module_parser.add_argument("--root", default=".", help="Project root directory")

    check_parser = subparsers.add_parser("check", help="Check required project files")
    check_parser.add_argument("--root", default=".", help="Project root directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        app_name = args.app_name or args.project_name.replace("-", "_")
        databases = [item.strip() for item in args.databases.split(",") if item.strip()]
        options = ProjectOptions(
            project_name=args.project_name,
            app_name=app_name,
            port=args.port,
            databases=databases,
            enable_auth=not args.disable_auth,
            enable_signing=not args.disable_signing,
            enable_i18n=not args.disable_i18n,
            enable_response_cache=not args.disable_response_cache,
            include_example=True,
        )
        render_project_files(Path(args.root), options)
        return 0
    if args.command == "add":
        created = add_version(args.version, args.root)
        for path in created:
            print(path)
        return 0
    if args.command == "make" and args.make_command == "module":
        created = make_module(args.version, args.module, args.root)
        for path in created:
            print(path)
        return 0
    if args.command == "check":
        issues = check_project(Path(args.root))
        if issues:
            for issue in issues:
                print(issue)
            return 1
        print("Project check passed")
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
