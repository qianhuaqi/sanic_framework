from __future__ import annotations

from pathlib import Path

from framework.error_codes import resolve_error_message


def _project_root() -> Path:
    return Path.cwd()


def version_from_path(path: str = "") -> str:
    parts = [part for part in str(path).split("/") if part]
    if parts and parts[0].startswith("v") and parts[0][1:].isdigit():
        return parts[0]
    return ""


def _request_version(request) -> str:
    if request is None:
        return ""
    return version_from_path(getattr(request, "path", ""))


def language_roots(version: str = "") -> list[Path]:
    root = _project_root()
    roots = []
    if version:
        roots.append(root / "app" / version / "language")
    roots.append(root / "app" / "language")
    roots.append(root / "framework" / "language")
    return [item for item in roots if item.exists()]


def module_map_path(version: str = "") -> Path | None:
    root = _project_root()
    candidates = []
    if version:
        candidates.append(root / "app" / version / "language" / "modules.ini")
    candidates.extend(
        [
            root / "app" / "language" / "modules.ini",
            root / "framework" / "modules.ini",
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def get_error_message(request, code, default=None) -> str:
    config = getattr(getattr(request, "app", None), "ctx", None)
    config = getattr(config, "config", None)
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
        errcode=None,
        errmsg=None,
    ):
        if errcode is not None:
            code = errcode
        if errmsg is not None:
            msg = errmsg
        if msg is None:
            msg = get_error_message(request, code)
        super().__init__(msg)
        self.code = code
        self.msg = msg
        self.errcode = code
        self.errmsg = msg
        self.status_code = status_code
        self.data = data or {}
