from __future__ import annotations

from pathlib import Path

from framework.error_codes import resolve_error_message


def _project_root() -> Path:
    return Path.cwd()


def _request_version(request) -> str:
    if request is None:
        return ""
    parts = [part for part in request.path.split("/") if part]
    if parts and parts[0].startswith("v") and parts[0][1:].isdigit():
        return parts[0]
    return ""


def _language_roots(request=None) -> list[Path]:
    root = _project_root()
    version = _request_version(request)
    roots = []
    if version:
        roots.append(root / "app" / version / "language")
    roots.append(root / "app" / "language")
    roots.append(root / "language")
    roots.append(root / "framework" / "language")
    return [item for item in roots if item.exists()]


def _module_map_path(request=None) -> Path | None:
    root = _project_root()
    version = _request_version(request)
    candidates = []
    if version:
        candidates.append(root / "app" / version / "language" / "modules.ini")
    candidates.extend(
        [
            root / "app" / "language" / "modules.ini",
            root / "language" / "modules.ini",
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
    roots = _language_roots(request)
    module_map_path = _module_map_path(request)
    if not roots or module_map_path is None:
        return default or str(code)
    return resolve_error_message(code, roots, locale=locale, module_map_path=module_map_path, default=default)


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
            msg = get_error_message(request, code, default="internal error")
        super().__init__(msg)
        self.code = code
        self.msg = msg
        self.errcode = code
        self.errmsg = msg
        self.status_code = status_code
        self.data = data or {}
