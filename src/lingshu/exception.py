from __future__ import annotations

from pathlib import Path

from lingshu.error_codes import resolve_error_message
from lingshu.system.context import current_app, current_request
from lingshu.system.sanic_adapter import get_app_config
from lingshu.versioning import normalize_version, version_from_path


def _project_root() -> Path:
    return Path.cwd()


def _request_version(request) -> str:
    if request is None:
        request = current_request.get()
    if request is None:
        return ""
    return version_from_path(getattr(request, "path", ""))


def language_roots(version: str = "") -> list[Path]:
    root = _project_root()
    roots = []
    if version:
        version = normalize_version(version)
        roots.append(root / "app" / version / "language")
    roots.append(root / "app" / "language")
    roots.append(Path(__file__).resolve().parent / "language")
    return [item for item in roots if item.exists()]


def module_map_path(version: str = "") -> Path | None:
    root = _project_root()
    candidates = []
    if version:
        version = normalize_version(version)
        candidates.append(root / "app" / version / "language" / "modules.ini")
    candidates.extend(
        [
            root / "app" / "language" / "modules.ini",
            Path(__file__).resolve().parent / "modules.ini",
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def get_error_message(request, code, default=None) -> str:
    if request is None:
        request = current_request.get()
    raw_app = getattr(request, "app", None) if request is not None else current_app.get()
    config = get_app_config(raw_app) if raw_app is not None else None
    locale = getattr(config, "language", "zh-CN")
    roots = language_roots(_request_version(request))
    map_path = module_map_path(_request_version(request))
    if not roots or map_path is None:
        return str(code)
    return resolve_error_message(code, roots, locale=locale, module_map_path=map_path, default=default)


def raise_code(request, code, status_code=400, data=None, default=None):
    raise APIException(code=code, msg=get_error_message(request, code, default=default), status_code=status_code, data=data)


class APIException(Exception):
    def __init__(
        self,
        code=500000,
        msg=None,
        status_code=500,
        data=None,
        request=None,
    ):
        if msg is None:
            msg = get_error_message(request, code)
        super().__init__(msg)
        self.code = code
        self.msg = msg
        self.status_code = status_code
        self.data = {} if data is None else data
