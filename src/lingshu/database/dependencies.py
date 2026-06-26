from __future__ import annotations

import importlib


class DatabaseDependencyError(RuntimeError):
    pass


def require_database_package(import_path: str, package_name: str, database_name: str):
    try:
        return importlib.import_module(import_path)
    except ModuleNotFoundError as exc:
        root_package = import_path.split(".", 1)[0]
        if exc.name == root_package or str(exc.name).startswith(f"{root_package}."):
            env_name = f"{database_name.upper()}_ENABLED"
            raise DatabaseDependencyError(
                f"Database '{database_name}' is enabled but Python package '{package_name}' is not installed. "
                f"Install dependencies with `pip install -r requirements.txt` or `pip install {package_name}`, "
                f"or set {env_name}=false."
            ) from exc
        raise
