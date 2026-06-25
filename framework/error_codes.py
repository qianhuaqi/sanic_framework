from __future__ import annotations

from collections.abc import Iterable
from configparser import ConfigParser
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


CANONICAL_LOCALES = ("zh-CN", "en-US")
LOCALE_ALIASES = {
    "cn": "zh-CN",
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh_cn": "zh-CN",
    "en": "en-US",
    "en-us": "en-US",
    "en_us": "en-US",
}


def normalize_locale_name(name: str) -> str:
    normalized = str(name).strip().replace("_", "-")
    lowered = normalized.lower()
    return LOCALE_ALIASES.get(lowered, normalized)


@dataclass
class ErrorCodeRecord:
    code: str
    module: str
    module_range: str
    section: str
    messages: dict[str, str] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        default_message = self.messages.get("zh-CN") or self.messages.get("en-US")
        if default_message is None and self.messages:
            default_message = next(iter(self.messages.values()))
        return {
            "code": self.code,
            "module": self.module,
            "module_range": self.module_range,
            "section": self.section,
            "default_message": default_message,
            "messages": dict(sorted(self.messages.items())),
            "sources": dict(sorted(self.sources.items())),
        }


@dataclass(frozen=True)
class ModuleRange:
    module: str
    range_expr: str
    start: int
    end: int

    def contains(self, code: int) -> bool:
        return self.start <= code <= self.end


def _candidate_locale_dirs(locale_root: Path, locale_name: str) -> list[Path]:
    canonical = normalize_locale_name(locale_name)
    if canonical == "zh-CN":
        aliases = ("zh-CN", "zh-cn", "zh_cn", "zh", "cn")
    elif canonical == "en-US":
        aliases = ("en-US", "en-us", "en_us", "en")
    else:
        aliases = (canonical,)
    for alias in aliases:
        path = locale_root / alias
        if path.exists():
            return [path]
    return []


def _normalize_locale_roots(locale_root: str | Path | Iterable[str | Path]) -> list[Path]:
    if isinstance(locale_root, (str, Path)):
        return [Path(locale_root)]
    return [Path(root) for root in locale_root]


def _format_source(locale_root: Path, ini_file: Path, section: str) -> str:
    relative_file = ini_file.relative_to(locale_root).as_posix()
    try:
        relative_root = locale_root.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        relative_root = locale_root.as_posix()
    return f"{relative_root}/{relative_file}:{section}"


def _parse_ini_file(file_path: Path) -> ConfigParser:
    parser = ConfigParser()
    parser.optionxform = str
    parser.read(file_path, encoding="utf-8")
    return parser


def _parse_module_range(expr: str) -> tuple[int, int]:
    value = str(expr).strip()
    if "-" in value:
        start_text, end_text = value.split("-", 1)
        start = int(start_text.strip())
        end = int(end_text.strip())
    else:
        start = end = int(value)
    if start > end:
        raise ValueError(f"Invalid module range: {expr!r}")
    return start, end


def parse_module_ranges(module_map_path: str | Path) -> list[ModuleRange]:
    path = Path(module_map_path)
    if not path.exists():
        raise FileNotFoundError(f"Module map not found: {path}")

    parser = ConfigParser()
    parser.optionxform = str
    parser.read(path, encoding="utf-8")
    if "Modules" not in parser:
        raise ValueError("Module map must contain a [Modules] section")

    ranges: list[ModuleRange] = []
    for range_expr, module_name in parser.items("Modules"):
        start, end = _parse_module_range(range_expr)
        ranges.append(
            ModuleRange(
                module=str(module_name).strip().lower(),
                range_expr=range_expr.strip(),
                start=start,
                end=end,
            )
        )

    ranges.sort(key=lambda item: (item.start, item.end))
    for index in range(1, len(ranges)):
        previous = ranges[index - 1]
        current = ranges[index]
        if current.start <= previous.end:
            raise ValueError(
                f"Overlapping module ranges: {previous.range_expr} ({previous.module}) and "
                f"{current.range_expr} ({current.module})"
            )
    return ranges


def _resolve_module_range(code: int, module_ranges: list[ModuleRange]) -> ModuleRange:
    for module_range in module_ranges:
        if module_range.contains(code):
            return module_range
    raise ValueError(f"Error code '{code}' does not belong to any configured module range")


def parse_error_code_catalog(
    locale_root: str | Path | Iterable[str | Path],
    module_map_path: str | Path | None = None,
) -> list[ErrorCodeRecord]:
    roots = [root for root in _normalize_locale_roots(locale_root) if root.exists()]
    if not roots:
        return []

    if module_map_path is None:
        module_map_path = Path(__file__).with_name("modules.ini")
    module_ranges = parse_module_ranges(module_map_path)

    records: dict[str, ErrorCodeRecord] = {}
    seen_sources: dict[tuple[str, str], tuple[int, str]] = {}

    for locale_name in CANONICAL_LOCALES:
        for root_index, root in enumerate(roots):
            for locale_dir in _candidate_locale_dirs(root, locale_name):
                for ini_file in sorted(locale_dir.rglob("*.ini")):
                    parser = _parse_ini_file(ini_file)
                    for section in parser.sections():
                        for code, message in parser.items(section):
                            normalized_code = str(code).strip()
                            if not normalized_code:
                                continue
                            code_value = int(normalized_code)
                            module_range = _resolve_module_range(code_value, module_ranges)
                            module_name = module_range.module
                            source = _format_source(root, ini_file, section)
                            key = (locale_name, normalized_code)
                            if key in seen_sources:
                                previous_root_index, previous_source = seen_sources[key]
                                if previous_root_index == root_index:
                                    raise ValueError(
                                        f"Duplicate error code '{normalized_code}' in locale '{locale_name}': "
                                        f"{previous_source} and {source}"
                                    )
                                continue
                            seen_sources[key] = (root_index, source)

                            record = records.get(normalized_code)
                            if record is None:
                                record = ErrorCodeRecord(
                                    code=normalized_code,
                                    module=module_name,
                                    module_range=module_range.range_expr,
                                    section=section,
                                )
                                records[normalized_code] = record
                            elif (
                                record.module != module_name
                                or record.module_range != module_range.range_expr
                                or record.section != section
                            ):
                                raise ValueError(
                                    f"Error code '{normalized_code}' has conflicting definitions: "
                                    f"{record.module}/{record.module_range}/{record.section} and "
                                    f"{module_name}/{module_range.range_expr}/{section}"
                                )

                            record.messages[locale_name] = str(message).strip()
                            record.sources[locale_name] = source

    return sorted(records.values(), key=lambda item: item.code)


def _cache_key_for_roots(locale_root: str | Path | Iterable[str | Path]) -> tuple[str, ...]:
    return tuple(str(root.resolve()) for root in _normalize_locale_roots(locale_root))


@lru_cache(maxsize=64)
def _parse_error_code_catalog_cached(
    roots: tuple[str, ...],
    module_map_path: str | None,
) -> tuple[ErrorCodeRecord, ...]:
    return tuple(parse_error_code_catalog([Path(root) for root in roots], module_map_path=module_map_path))


def parse_error_code_catalog_cached(
    locale_root: str | Path | Iterable[str | Path],
    module_map_path: str | Path | None = None,
) -> list[ErrorCodeRecord]:
    roots = _cache_key_for_roots(locale_root)
    module_map = str(Path(module_map_path).resolve()) if module_map_path is not None else None
    return list(_parse_error_code_catalog_cached(roots, module_map))


def build_error_code_index(
    locale_root: str | Path | Iterable[str | Path],
    module_map_path: str | Path | None = None,
) -> dict[str, object]:
    records = parse_error_code_catalog_cached(locale_root, module_map_path=module_map_path)
    if module_map_path is None:
        module_map_path = Path(__file__).with_name("modules.ini")
    module_ranges = parse_module_ranges(module_map_path)
    module_buckets = {
        module_range.module: {
            "module": module_range.module,
            "range": module_range.range_expr,
            "total": 0,
            "items": [],
        }
        for module_range in module_ranges
    }
    for record in records:
        bucket = module_buckets.setdefault(
            record.module,
            {
                "module": record.module,
                "range": record.module_range,
                "total": 0,
                "items": [],
            },
        )
        bucket["items"].append(record.to_dict())
        bucket["total"] += 1
    locales = list(CANONICAL_LOCALES)
    return {
        "locales": locales,
        "total": len(records),
        "modules": list(module_buckets.values()),
        "codes": [record.to_dict() for record in records],
    }


def resolve_error_message(
    code: int | str,
    locale_root: str | Path | Iterable[str | Path],
    locale: str = "zh-CN",
    module_map_path: str | Path | None = None,
    default: str | None = None,
) -> str:
    normalized_code = str(code).strip()
    normalized_locale = normalize_locale_name(locale)
    try:
        records = parse_error_code_catalog_cached(locale_root, module_map_path=module_map_path)
    except (FileNotFoundError, ValueError):
        return default or normalized_code
    for record in records:
        if record.code == normalized_code:
            return (
                record.messages.get(normalized_locale)
                or record.messages.get("zh-CN")
                or record.messages.get("en-US")
                or default
                or normalized_code
            )
    return default or normalized_code
