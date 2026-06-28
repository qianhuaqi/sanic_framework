"""Static configuration schema, secret handling, and immutable snapshots."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol, TypeVar, runtime_checkable

from lingshu.core.errors import ConfigurationError, FatalScope
from lingshu.core.identifiers import RevisionId

_KEY_SEGMENT = re.compile(r"^[a-z][a-z0-9_]*$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_T = TypeVar("_T")


class ConfigSourceKind(StrEnum):
    """Ordered P1 startup configuration source kinds."""

    DEFAULTS = "defaults"
    FILE = "file"
    ENVIRONMENT = "environment"
    CLI = "cli"
    PROGRAMMATIC = "programmatic"

    @property
    def precedence(self) -> int:
        """Return the frozen low-to-high precedence rank."""

        return {
            ConfigSourceKind.DEFAULTS: 0,
            ConfigSourceKind.FILE: 1,
            ConfigSourceKind.ENVIRONMENT: 2,
            ConfigSourceKind.CLI: 3,
            ConfigSourceKind.PROGRAMMATIC: 4,
        }[self]


class RedactionClass(StrEnum):
    """Configuration disclosure class."""

    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    SECRET = "secret"


class ReloadPolicy(StrEnum):
    """P1 metadata for later reload planning."""

    STATIC = "static"
    RESTART_REQUIRED = "restart_required"


@dataclass(frozen=True, slots=True)
class SecretRef:
    """Opaque reference resolved by a configured secret provider."""

    reference: str

    def __post_init__(self) -> None:
        if not self.reference or len(self.reference) > 512 or _CONTROL.search(self.reference):
            raise ValueError("secret reference must be non-empty, bounded, and control-free")

    def __repr__(self) -> str:
        return "SecretRef(<redacted>)"


class SecretValue:
    """Resolved secret with explicit reveal and permanently redacted display."""

    __slots__ = ("_reference", "_value")

    _reference: str | None
    _value: str

    def __init__(self, value: str, *, reference: str | None = None) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError("secret value must be a non-empty string")
        object.__setattr__(self, "_value", value)
        object.__setattr__(self, "_reference", reference)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("SecretValue is immutable")

    def reveal(self) -> str:
        """Return plaintext only at an explicit consumption point."""

        return self._value

    def __repr__(self) -> str:
        return "SecretValue(<redacted>)"

    def __str__(self) -> str:
        return "<redacted>"


@runtime_checkable
class SecretProvider(Protocol):
    """Resolve one secret reference before readiness."""

    def resolve(self, reference: str) -> str:
        """Return plaintext for ``reference`` or raise an ordinary exception."""


type ConfigScalar = str | int | float | bool | None | SecretValue
type ConfigValue = ConfigScalar | tuple[ConfigValue, ...] | Mapping[str, ConfigValue]
type ValueNormalizer = Callable[[object], object]


class _Missing:
    __slots__ = ()


_MISSING = _Missing()


def _identity(value: object) -> object:
    return value


@dataclass(frozen=True, slots=True)
class ConfigField:
    """Schema metadata and value normalizer for one canonical dotted path."""

    normalizer: ValueNormalizer = _identity
    required: bool = False
    default: object = _MISSING
    redaction: RedactionClass = RedactionClass.INTERNAL
    reload_policy: ReloadPolicy = ReloadPolicy.RESTART_REQUIRED

    def __post_init__(self) -> None:
        if not callable(self.normalizer):
            raise TypeError("configuration field normalizer must be callable")
        if not isinstance(self.default, _Missing):
            object.__setattr__(self, "default", _freeze_raw_value(self.default))

    @property
    def has_default(self) -> bool:
        return not isinstance(self.default, _Missing)


@dataclass(frozen=True, slots=True)
class ConfigSchema:
    """Versioned immutable collection of canonical configuration fields."""

    version: int
    fields: Mapping[str, ConfigField]

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("configuration schema version must be positive")

        normalized: dict[str, ConfigField] = {}
        for raw_key, field in self.fields.items():
            key = normalize_config_key(raw_key)
            if key in normalized:
                raise ValueError(f"duplicate normalized schema key: {key}")
            normalized[key] = field
        ordered_keys = tuple(normalized)
        for index, key in enumerate(ordered_keys):
            prefix = f"{key}."
            if any(other.startswith(prefix) for other in ordered_keys[index + 1 :]):
                raise ValueError(f"configuration schema paths overlap: {key}")
            if any(key.startswith(f"{other}.") for other in ordered_keys[:index]):
                raise ValueError(f"configuration schema paths overlap: {key}")
        object.__setattr__(self, "fields", MappingProxyType(normalized))


@dataclass(frozen=True, slots=True)
class ConfigSource:
    """One immutable startup configuration source."""

    kind: ConfigSourceKind
    values: Mapping[str, object]
    name: str | None = None
    schema_version: int | None = None

    def __post_init__(self) -> None:
        if self.kind is ConfigSourceKind.DEFAULTS:
            raise ValueError("defaults are owned by ConfigSchema")
        if self.kind is ConfigSourceKind.FILE and self.schema_version is None:
            raise ValueError("file configuration sources require schema_version")
        if self.name is not None and (
            not self.name or len(self.name) > 128 or _CONTROL.search(self.name)
        ):
            raise ValueError("source name must be non-empty, bounded, and control-free")
        object.__setattr__(self, "values", _freeze_raw_mapping(self.values))


@dataclass(frozen=True, slots=True)
class SourceManifestEntry:
    """Safe source provenance without raw values."""

    kind: ConfigSourceKind
    name: str
    keys: tuple[str, ...]


@dataclass(frozen=True, slots=True, repr=False)
class ConfigSnapshot:
    """Immutable validated startup configuration."""

    schema_version: int
    revision_id: RevisionId
    source_manifest: tuple[SourceManifestEntry, ...]
    values: Mapping[str, ConfigValue]
    redaction_metadata: Mapping[str, RedactionClass]
    reload_metadata: Mapping[str, ReloadPolicy]
    canonical_bytes: bytes

    def __getitem__(self, path: str) -> ConfigValue:
        return self.values[normalize_config_key(path)]

    def get(self, path: str, default: _T | None = None) -> ConfigValue | _T | None:
        return self.values.get(normalize_config_key(path), default)

    def require(self, path: str, expected_type: type[_T]) -> _T:
        """Return a value only when its runtime type matches exactly enough for consumption."""

        key = normalize_config_key(path)
        try:
            value = self.values[key]
        except KeyError as exc:
            raise KeyError(key) from exc
        if not isinstance(value, expected_type):
            raise TypeError(f"configuration value {key!r} is not {expected_type.__name__}")
        return value

    def redacted(self, *, include_internal: bool = False) -> Mapping[str, object]:
        """Return a nested, immutable-safe diagnostic view."""

        flat: dict[str, object] = {}
        for key, value in self.values.items():
            redaction = self.redaction_metadata[key]
            if redaction is RedactionClass.PUBLIC or (
                redaction is RedactionClass.INTERNAL and include_internal
            ):
                flat[key] = _thaw_nonsecret(value)
            else:
                flat[key] = f"<{redaction.value}>"
        return MappingProxyType(_unflatten(flat))

    def __repr__(self) -> str:
        return (
            "ConfigSnapshot("
            f"schema_version={self.schema_version}, "
            f"revision_id={self.revision_id!s}, "
            f"keys={tuple(self.values)})"
        )


def normalize_config_key(raw_key: str) -> str:
    """Normalize a dotted key to lowercase underscore-separated canonical form."""

    if not isinstance(raw_key, str):
        raise TypeError("configuration keys must be strings")
    segments: list[str] = []
    for raw_segment in raw_key.split("."):
        segment = raw_segment.strip().casefold().replace("-", "_")
        if _KEY_SEGMENT.fullmatch(segment) is None:
            raise ValueError(f"invalid configuration key segment: {raw_segment!r}")
        segments.append(segment)
    return ".".join(segments)


def as_string(value: object) -> str:
    """Normalize a configuration value as a string."""

    if not isinstance(value, str):
        raise TypeError("expected string")
    return value


def as_integer(value: object) -> int:
    """Normalize an integer without accepting bool or expression syntax."""

    if isinstance(value, bool):
        raise TypeError("expected integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 10)
    raise TypeError("expected integer")


def as_float(value: object) -> float:
    """Normalize a finite float."""

    if isinstance(value, bool):
        raise TypeError("expected float")
    if isinstance(value, int | float | str):
        normalized = float(value)
        if math.isfinite(normalized):
            return normalized
    raise ValueError("expected finite float")


def as_boolean(value: object) -> bool:
    """Normalize a bounded boolean vocabulary without evaluating code."""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ValueError("expected boolean")


def as_string_tuple(value: object) -> tuple[str, ...]:
    """Normalize a sequence of strings; strings are not split implicitly."""

    if not isinstance(value, list | tuple):
        raise TypeError("expected a string sequence")
    if not all(isinstance(item, str) for item in value):
        raise TypeError("expected a string sequence")
    return tuple(value)


def environment_source(
    environ: Mapping[str, str],
    *,
    prefix: str = "LINGSHU_",
    name: str = "environment",
) -> ConfigSource:
    """Create an environment source using ``__`` as the nested-key separator."""

    if not prefix:
        raise ValueError("environment prefix must not be empty")
    values: dict[str, object] = {}
    for variable, value in environ.items():
        if variable.startswith(prefix):
            suffix = variable[len(prefix) :]
            key = ".".join(suffix.split("__"))
            values[key] = value
    return ConfigSource(ConfigSourceKind.ENVIRONMENT, values, name=name)


def build_config_snapshot(
    schema: ConfigSchema,
    sources: tuple[ConfigSource, ...] | list[ConfigSource] = (),
    *,
    secret_provider: SecretProvider | None = None,
) -> ConfigSnapshot:
    """Normalize, validate, resolve, freeze, and hash static startup configuration."""

    ordered = _order_sources(sources)
    merged: dict[str, object] = {}
    manifest: list[SourceManifestEntry] = []

    defaults = {key: field.default for key, field in schema.fields.items() if field.has_default}
    if defaults:
        merged.update(defaults)
        manifest.append(
            SourceManifestEntry(
                ConfigSourceKind.DEFAULTS, "schema defaults", tuple(sorted(defaults))
            )
        )

    for source in ordered:
        if source.kind is ConfigSourceKind.FILE and source.schema_version != schema.version:
            raise _configuration_error(
                "config.schema_mismatch",
                "Configuration schema version does not match.",
                details={"expected": schema.version, "received": source.schema_version},
            )
        flattened = _flatten_source(source.values, frozenset(schema.fields))
        unknown = tuple(sorted(set(flattened) - set(schema.fields)))
        if unknown:
            raise _configuration_error(
                "config.unknown_key",
                "Configuration contains unknown keys.",
                details={"keys": unknown},
            )
        for key, value in flattened.items():
            if key in merged and isinstance(merged[key], Mapping) and isinstance(value, Mapping):
                merged[key] = _deep_merge(merged[key], value)
            else:
                merged[key] = value
        manifest.append(
            SourceManifestEntry(
                source.kind,
                source.name or source.kind.value,
                tuple(sorted(flattened)),
            )
        )

    missing = tuple(
        key for key, field in schema.fields.items() if field.required and key not in merged
    )
    if missing:
        raise _configuration_error(
            "config.missing_required",
            "Required configuration values are missing.",
            details={"keys": missing},
        )

    normalized_values: dict[str, ConfigValue] = {}
    for key, raw_value in merged.items():
        field = schema.fields[key]
        normalized_values[key] = _normalize_field(
            key,
            field,
            raw_value,
            secret_provider=secret_provider,
        )

    redaction = MappingProxyType({key: schema.fields[key].redaction for key in normalized_values})
    reload_metadata = MappingProxyType(
        {key: schema.fields[key].reload_policy for key in normalized_values}
    )
    immutable_values = MappingProxyType(dict(sorted(normalized_values.items())))
    canonical = _canonical_snapshot_bytes(
        schema.version, immutable_values, redaction, reload_metadata
    )

    return ConfigSnapshot(
        schema_version=schema.version,
        revision_id=RevisionId.from_canonical_bytes(canonical),
        source_manifest=tuple(manifest),
        values=immutable_values,
        redaction_metadata=redaction,
        reload_metadata=reload_metadata,
        canonical_bytes=canonical,
    )


def _order_sources(
    sources: tuple[ConfigSource, ...] | list[ConfigSource],
) -> tuple[ConfigSource, ...]:
    by_kind: dict[ConfigSourceKind, ConfigSource] = {}
    for source in sources:
        if source.kind in by_kind:
            raise _configuration_error(
                "config.duplicate_source",
                "Only one source of each configuration kind is allowed in P1.",
                details={"kind": source.kind.value},
            )
        by_kind[source.kind] = source
    return tuple(sorted(by_kind.values(), key=lambda source: source.kind.precedence))


def _flatten_source(
    values: Mapping[str, object],
    schema_keys: frozenset[str],
) -> dict[str, object]:
    flattened: dict[str, object] = {}

    def visit(mapping: Mapping[str, object], prefix: str | None = None) -> None:
        for raw_key, value in mapping.items():
            normalized = normalize_config_key(raw_key)
            key = f"{prefix}.{normalized}" if prefix else normalized
            if key in schema_keys:
                if key in flattened:
                    raise _configuration_error(
                        "config.duplicate_key",
                        "A configuration source contains duplicate normalized keys.",
                        details={"key": key},
                    )
                flattened[key] = value
            elif isinstance(value, Mapping):
                visit(value, key)
            else:
                if key in flattened:
                    raise _configuration_error(
                        "config.duplicate_key",
                        "A configuration source contains duplicate normalized keys.",
                        details={"key": key},
                    )
                flattened[key] = value

    visit(values)
    return flattened


def _normalize_field(
    key: str,
    field: ConfigField,
    raw_value: object,
    *,
    secret_provider: SecretProvider | None,
) -> ConfigValue:
    if field.redaction is RedactionClass.SECRET:
        return _resolve_secret(key, raw_value, secret_provider)
    if isinstance(raw_value, SecretRef | SecretValue):
        raise _configuration_error(
            "config.secret_misclassified",
            "Secret values require a secret schema field.",
            details={"key": key},
        )
    try:
        normalized = field.normalizer(raw_value)
        return _freeze_config_value(normalized, allow_secret=False)
    except ConfigurationError:
        raise
    except Exception as exc:
        raise _configuration_error(
            "config.invalid",
            "A configuration value is invalid.",
            details={"key": key},
            cause=exc,
        ) from exc


def _resolve_secret(
    key: str,
    raw_value: object,
    provider: SecretProvider | None,
) -> SecretValue:
    if isinstance(raw_value, SecretValue):
        return raw_value
    if not isinstance(raw_value, SecretRef):
        raise _configuration_error(
            "config.secret_required",
            "Secret configuration requires SecretRef or SecretValue.",
            details={"key": key},
        )
    if provider is None:
        raise _configuration_error(
            "config.secret_provider_missing",
            "A secret provider is required before readiness.",
            details={"key": key},
        )
    try:
        plaintext = provider.resolve(raw_value.reference)
        return SecretValue(plaintext, reference=raw_value.reference)
    except Exception as exc:
        raise _configuration_error(
            "config.secret_resolution_failed",
            "A required secret could not be resolved.",
            details={"key": key},
            cause=exc,
        ) from exc


def _freeze_raw_mapping(values: Mapping[str, object]) -> Mapping[str, object]:
    frozen: dict[str, object] = {}
    for key, value in values.items():
        if not isinstance(key, str):
            raise TypeError("configuration source keys must be strings")
        frozen[key] = _freeze_raw_value(value)
    return MappingProxyType(frozen)


def _freeze_raw_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _freeze_raw_mapping(value)
    if isinstance(value, list | tuple):
        return tuple(_freeze_raw_value(item) for item in value)
    if isinstance(value, str | int | float | bool | SecretRef | SecretValue) or value is None:
        return value
    raise TypeError(f"unsupported configuration source value: {type(value).__name__}")


def _freeze_config_value(value: object, *, allow_secret: bool = True) -> ConfigValue:
    if isinstance(value, SecretValue):
        if not allow_secret:
            raise TypeError("secret values require a secret schema field")
        return value
    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("configuration floats must be finite")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, ConfigValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("configuration mapping keys must be strings")
            frozen[key] = _freeze_config_value(item, allow_secret=allow_secret)
        return MappingProxyType(frozen)
    if isinstance(value, list | tuple):
        return tuple(_freeze_config_value(item, allow_secret=allow_secret) for item in value)
    raise TypeError(f"unsupported normalized configuration value: {type(value).__name__}")


def _deep_merge(lower: object, higher: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(lower, Mapping):
        return higher
    merged: dict[str, object] = dict(lower)
    for key, value in higher.items():
        if key in merged and isinstance(merged[key], Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return MappingProxyType(merged)


def _canonical_snapshot_bytes(
    schema_version: int,
    values: Mapping[str, ConfigValue],
    redaction: Mapping[str, RedactionClass],
    reload_metadata: Mapping[str, ReloadPolicy],
) -> bytes:
    document = {
        "schema_version": schema_version,
        "values": {
            key: _canonical_value(key, value, redaction[key]) for key, value in values.items()
        },
        "redaction": {key: value.value for key, value in sorted(redaction.items())},
        "reload": {key: value.value for key, value in sorted(reload_metadata.items())},
    }
    return json.dumps(
        document,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _canonical_value(
    path: str,
    value: ConfigValue,
    redaction: RedactionClass,
) -> object:
    if isinstance(value, SecretValue):
        if value._reference is None:
            return {"$secret": path}
        digest = hashlib.sha256(value._reference.encode("utf-8")).hexdigest()
        return {"$secret_ref_sha256": digest}
    if redaction is RedactionClass.SENSITIVE:
        plain = _canonical_plain_value(path, value)
        encoded = json.dumps(
            plain,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return {"$sensitive_sha256": hashlib.sha256(encoded).hexdigest()}
    return _canonical_plain_value(path, value)


def _canonical_plain_value(path: str, value: ConfigValue) -> object:
    if isinstance(value, SecretValue):
        raise TypeError("secret value reached a non-secret canonical path")
    if isinstance(value, Mapping):
        return {
            key: _canonical_plain_value(f"{path}.{key}", item)
            for key, item in sorted(value.items())
        }
    if isinstance(value, tuple):
        return [_canonical_plain_value(path, item) for item in value]
    return value


def _thaw_nonsecret(value: ConfigValue) -> object:
    if isinstance(value, SecretValue):
        return "<secret>"
    if isinstance(value, Mapping):
        return {key: _thaw_nonsecret(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_nonsecret(item) for item in value]
    return value


def _unflatten(values: Mapping[str, object]) -> dict[str, object]:
    root: dict[str, object] = {}
    for path, value in values.items():
        cursor = root
        segments = path.split(".")
        for segment in segments[:-1]:
            child = cursor.setdefault(segment, {})
            if not isinstance(child, dict):
                raise RuntimeError("configuration paths overlap")
            cursor = child
        cursor[segments[-1]] = value
    return root


def _configuration_error(
    code: str,
    message: str,
    *,
    details: Mapping[str, object] | None = None,
    cause: Exception | None = None,
) -> ConfigurationError:
    return ConfigurationError(
        code,
        message,
        fatal_scope=FatalScope.WORKER,
        safe_details=details,
        cause=cause,
    )


__all__ = (
    "ConfigField",
    "ConfigSchema",
    "ConfigSnapshot",
    "ConfigSource",
    "ConfigSourceKind",
    "ConfigValue",
    "RedactionClass",
    "ReloadPolicy",
    "SecretProvider",
    "SecretRef",
    "SecretValue",
    "SourceManifestEntry",
    "ValueNormalizer",
    "as_boolean",
    "as_float",
    "as_integer",
    "as_string",
    "as_string_tuple",
    "build_config_snapshot",
    "environment_source",
    "normalize_config_key",
)
