from __future__ import annotations

import re


VERSION_PATTERN = re.compile(r"^v[0-9]+(?:_[A-Za-z0-9]+)*$")


def normalize_version(version: str) -> str:
    normalized = str(version).strip()
    if not VERSION_PATTERN.fullmatch(normalized):
        raise ValueError("Version name must look like v1, v2, v1_admin, or v2_partner")
    return normalized


def version_from_path(path: str = "") -> str:
    parts = [part for part in str(path).split("/") if part]
    if not parts:
        return ""
    try:
        return normalize_version(parts[0])
    except ValueError:
        return ""
