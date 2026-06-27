"""Shared AST import scanner for architecture boundary tests.

All architecture tests use this single scanner instead of maintaining
separate copies of `_extract_imports`. This ensures consistent behaviour:

- SyntaxError fails closed (propagates, never returns empty list).
- Absolute imports: `import x` → `x`.
- Absolute ImportFrom: `from x import y` → records `x` and `x.y`.
- Relative imports: `from . import y` or `from ..core import z` are
  resolved using the file's package path derived from its location
  relative to the repository root.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _file_to_module_path(file_path: Path, repo_root: Path = ROOT) -> str:
    """Derive the Python dotted package path of a file relative to root.

    For example: ROOT/src/lingshu/core/types.py → "lingshu.core.types"
    """
    try:
        rel = file_path.relative_to(repo_root)
    except ValueError:
        return ""
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]  # strip .py
    # Remove 'src' prefix if present (src/lingshu/... → lingshu/...)
    if parts and parts[0] == "src":
        parts = parts[1:]
    return ".".join(parts)


def _resolve_relative_import(
    level: int,
    module: str | None,
    alias_name: str,
    file_path: Path,
    repo_root: Path = ROOT,
) -> list[str]:
    """Resolve a relative import to one or more absolute candidate paths.

    For `from ...core import types` in package `lingshu.security.auth.base`:
    - level=3 means go up 3 levels from the file's package.
    """
    file_module = _file_to_module_path(file_path, repo_root)
    if not file_module:
        return []

    if file_path.name != "__init__.py":
        if "." in file_module:
            file_package = file_module.rsplit(".", 1)[0]
        else:
            file_package = ""
    else:
        file_package = file_module

    package_parts = file_package.split(".") if file_package else []

    up = level - 1
    if up > len(package_parts):
        return [alias_name]

    base_parts = package_parts[: len(package_parts) - up] if up > 0 else package_parts[:]

    candidates = []

    if module:
        full_parts = base_parts + [module]
        base_dotted = ".".join(full_parts)
        candidates.append(base_dotted)
        candidates.append(f"{base_dotted}.{alias_name}")
    else:
        if base_parts:
            candidates.append(".".join(base_parts + [alias_name]))
        else:
            candidates.append(alias_name)

    return candidates


def extract_imports(file_path: Path, repo_root: Path = ROOT) -> list[str]:
    """Extract all import targets from a Python file using AST.

    Fails closed on SyntaxError — a file that cannot be parsed is a real
    problem and must not be silently skipped.

    For each import, records the full resolved dotted path(s):
    - `import x` → ["x"]
    - `import x.y` → ["x.y"]
    - `from x import y` → ["x", "x.y"]
    - `from lingshu import system` → ["lingshu", "lingshu.system"]
    - `from ...core import types` → resolved using file's package path
    """
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            module = node.module
            level = node.level

            for alias in node.names:
                if level > 0:
                    resolved = _resolve_relative_import(level, module, alias.name, file_path, repo_root)
                    imports.extend(resolved)
                else:
                    if module:
                        imports.append(module)
                        imports.append(f"{module}.{alias.name}")
                    else:
                        imports.append(alias.name)

    return imports


def collect_py_files(dir_path: Path) -> list[Path]:
    """Return all .py files under dir_path, or empty list if dir doesn't exist."""
    if not dir_path.exists():
        return []
    return list(dir_path.rglob("*.py"))
