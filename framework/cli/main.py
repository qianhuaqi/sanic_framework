from __future__ import annotations

import argparse
import re
from pathlib import Path
import sys

from framework.cli.project import ProjectOptions
from framework.cli.project import check_project
from framework.cli.project import render_scaffold_template
from framework.cli.project import render_project_files
from framework.versioning import normalize_version


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


def require_version(version: str, root: str | Path = ".") -> Path:
    version_name = normalize_version(version)
    version_root = Path(root).resolve() / "app" / version_name
    if not version_root.exists():
        raise ValueError(f"Version '{version_name}' does not exist. Run: sanic-framework add {version_name}")
    return version_root


def normalize_module_name(module: str) -> str:
    normalized = module.strip().replace("-", "_").lower()
    if not MODULE_PATTERN.match(normalized):
        raise ValueError("Module name must use snake_case, such as demo or user_profile")
    return normalized


def normalize_table_name(table: str) -> str:
    return normalize_module_name(table)


def normalize_business_name(name: str) -> str:
    return normalize_module_name(name)


def _pascal_case(value: str) -> str:
    return "".join(part.capitalize() for part in value.split("_") if part)


def _route_import_line(version_name: str, module_name: str) -> str:
    return f"    from app.{version_name}.controller.{module_name} import bp as {version_name}_{module_name}_bp\n"


def _route_append_line(version_name: str, module_name: str) -> str:
    return f"    blueprints.append({version_name}_{module_name}_bp)\n"


def _register_module_route(root_path: Path, version_name: str, module_name: str) -> bool:
    route_path = root_path / "app" / "route.py"
    if not route_path.exists():
        return False
    text = route_path.read_text(encoding="utf-8")
    import_line = _route_import_line(version_name, module_name)
    append_line = _route_append_line(version_name, module_name)
    changed = False
    if import_line not in text:
        marker = "    from app.controller.health import bp as health_bp\n"
        if marker in text:
            text = text.replace(marker, marker + import_line, 1)
        else:
            text = text.replace("def get_blueprints(config=None):\n", "def get_blueprints(config=None):\n" + import_line, 1)
        changed = True
    if append_line not in text:
        marker = "    blueprints = [health_bp]\n"
        if marker in text:
            text = text.replace(marker, marker + append_line, 1)
            changed = True
    if changed:
        route_path.write_text(text, encoding="utf-8")
    return changed


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
        version_root / "model" / "table",
        version_root / "model" / "business",
        version_root / "view",
    ):
        existed = directory.exists()
        _touch_init(directory)
        if not existed:
            created.append(directory)

    for directory in (
        version_root / "language",
        version_root / "language" / "zh-CN",
        version_root / "language" / "zh-CN" / "ERROR",
        version_root / "language" / "en-US",
        version_root / "language" / "en-US" / "ERROR",
    ):
        existed = directory.exists()
        directory.mkdir(parents=True, exist_ok=True)
        if not existed:
            created.append(directory)

    return created


def make_module(version: str, module: str, root: str | Path = ".") -> list[Path]:
    root_path = Path(root).resolve()
    version_name = normalize_version(version)
    module_name = normalize_module_name(module)
    model_class = f"{_pascal_case(module_name)}Model"
    version_root = require_version(version_name, root_path)
    docs_root = root_path / "public" / "docs" / version_name
    created: list[Path] = []

    view_dir = version_root / "view" / module_name
    docs_root.mkdir(parents=True, exist_ok=True)
    _touch_init(view_dir)

    controller = render_scaffold_template(
        "controller.py.j2",
        version_name=version_name,
        module_name=module_name,
        model_class=model_class,
    )
    model = render_scaffold_template("table_model.py.j2", model_class=model_class, table_name=module_name)
    view = render_scaffold_template("view.html.j2", version_name=version_name, module_name=module_name)
    docs = render_scaffold_template("docs.md.j2", version_name=version_name, module_name=module_name)
    files = {
        version_root / "controller" / f"{module_name}.py": controller,
        version_root / "model" / "table" / f"{module_name}.py": model,
        view_dir / "index.html": view,
        docs_root / f"{module_name}.md": docs,
    }
    for path, content in files.items():
        if _write_if_missing(path, content):
            created.append(path)
    if _register_module_route(root_path, version_name, module_name):
        created.append(root_path / "app" / "route.py")
    return created


def make_model(version: str, table: str, root: str | Path = ".") -> list[Path]:
    root_path = Path(root).resolve()
    version_name = normalize_version(version)
    require_version(version_name, root_path)
    table_name = normalize_table_name(table)
    model_class = f"{_pascal_case(table_name)}Model"
    created: list[Path] = []
    model = render_scaffold_template("table_model.py.j2", model_class=model_class, table_name=table_name)
    path = root_path / "app" / version_name / "model" / "table" / f"{table_name}.py"
    if _write_if_missing(path, model):
        created.append(path)
    return created


def make_business_model(version: str, business: str, root: str | Path = ".") -> list[Path]:
    root_path = Path(root).resolve()
    version_name = normalize_version(version)
    require_version(version_name, root_path)
    business_name = normalize_business_name(business)
    model_class = f"{_pascal_case(business_name)}BusinessModel"
    created: list[Path] = []
    model = render_scaffold_template(
        "business_model.py.j2",
        model_class=model_class,
        business_name=business_name,
    )
    path = root_path / "app" / version_name / "model" / "business" / f"{business_name}.py"
    if _write_if_missing(path, model):
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
    model_parser = make_subparsers.add_parser("model", help="Create a table model")
    model_parser.add_argument("version", help="Version name, for example v1")
    model_parser.add_argument("table", help="Physical table name, for example a_b")
    model_parser.add_argument("--root", default=".", help="Project root directory")
    business_model_parser = make_subparsers.add_parser("business-model", help="Create a business model")
    business_model_parser.add_argument("version", help="Version name, for example v1")
    business_model_parser.add_argument("business", help="Business model name, for example permission_assign")
    business_model_parser.add_argument("--root", default=".", help="Project root directory")

    check_parser = subparsers.add_parser("check", help="Check required project files")
    check_parser.add_argument("--root", default=".", help="Project root directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
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
                include_example=False,
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
        if args.command == "make" and args.make_command == "model":
            created = make_model(args.version, args.table, args.root)
            for path in created:
                print(path)
            return 0
        if args.command == "make" and args.make_command == "business-model":
            created = make_business_model(args.version, args.business, args.root)
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
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
