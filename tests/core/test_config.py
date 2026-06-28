from __future__ import annotations

from collections.abc import Mapping

import pytest

from lingshu.core.config import (
    ConfigField,
    ConfigSchema,
    ConfigSource,
    ConfigSourceKind,
    RedactionClass,
    ReloadPolicy,
    SecretRef,
    SecretValue,
    as_boolean,
    as_integer,
    as_string,
    as_string_tuple,
    build_config_snapshot,
    environment_source,
    normalize_config_key,
)
from lingshu.core.errors import ConfigurationError


class Provider:
    def __init__(self, values: Mapping[str, str]) -> None:
        self.values = values

    def resolve(self, reference: str) -> str:
        return self.values[reference]


def schema() -> ConfigSchema:
    return ConfigSchema(
        1,
        {
            "server.host": ConfigField(
                as_string, default="127.0.0.1", redaction=RedactionClass.PUBLIC
            ),
            "server.port": ConfigField(
                as_integer, default=8000, redaction=RedactionClass.PUBLIC
            ),
            "server.debug": ConfigField(as_boolean, default=False),
            "features.flags": ConfigField(default={"a": True, "nested": {"x": 1}}),
            "features.names": ConfigField(as_string_tuple, default=("base",)),
            "database.password": ConfigField(
                required=True, redaction=RedactionClass.SECRET
            ),
            "token": ConfigField(required=True, redaction=RedactionClass.SENSITIVE),
            "worker.count": ConfigField(
                as_integer, default=1, reload_policy=ReloadPolicy.STATIC
            ),
        },
    )


def secret_source() -> ConfigSource:
    return ConfigSource(
        ConfigSourceKind.PROGRAMMATIC,
        {"database.password": SecretRef("db/main"), "token": "opaque-token"},
    )


def test_precedence_is_deterministic_and_source_order_is_irrelevant() -> None:
    sources = [
        ConfigSource(ConfigSourceKind.CLI, {"server.port": 9400}),
        ConfigSource(
            ConfigSourceKind.FILE, {"server": {"port": 8100}}, schema_version=1
        ),
        environment_source({"LINGSHU_SERVER__PORT": "8200"}),
        ConfigSource(
            ConfigSourceKind.PROGRAMMATIC,
            {
                "server.port": 9500,
                "database.password": SecretRef("db/main"),
                "token": "x",
            },
        ),
    ]
    first = build_config_snapshot(
        schema(), sources, secret_provider=Provider({"db/main": "secret"})
    )
    second = build_config_snapshot(
        schema(),
        list(reversed(sources)),
        secret_provider=Provider({"db/main": "secret"}),
    )
    assert first["server.port"] == 9500
    assert first.revision_id == second.revision_id
    assert [entry.kind for entry in first.source_manifest] == [
        ConfigSourceKind.DEFAULTS,
        ConfigSourceKind.FILE,
        ConfigSourceKind.ENVIRONMENT,
        ConfigSourceKind.CLI,
        ConfigSourceKind.PROGRAMMATIC,
    ]


def test_nested_mappings_merge_and_sequences_replace() -> None:
    snapshot = build_config_snapshot(
        schema(),
        [
            ConfigSource(
                ConfigSourceKind.FILE,
                {
                    "features": {
                        "flags": {"b": True, "nested": {"y": 2}},
                        "names": ["file"],
                    }
                },
                schema_version=1,
            ),
            ConfigSource(
                ConfigSourceKind.PROGRAMMATIC,
                {
                    "features.flags": {"nested": {"x": 9}},
                    "features.names": ["programmatic"],
                    "database.password": SecretValue("secret"),
                    "token": "x",
                },
            ),
        ],
    )
    flags = snapshot["features.flags"]
    assert isinstance(flags, Mapping)
    assert flags == {"a": True, "b": True, "nested": {"x": 9, "y": 2}}
    assert snapshot["features.names"] == ("programmatic",)


def test_unknown_duplicate_normalized_and_duplicate_source_fail() -> None:
    with pytest.raises(ConfigurationError) as unknown:
        build_config_snapshot(
            schema(),
            [
                ConfigSource(
                    ConfigSourceKind.PROGRAMMATIC,
                    {"unknown": 1, "database.password": SecretValue("s"), "token": "x"},
                )
            ],
        )
    assert unknown.value.code == "config.unknown_key"

    with pytest.raises(ConfigurationError) as duplicate:
        build_config_snapshot(
            schema(),
            [
                ConfigSource(
                    ConfigSourceKind.PROGRAMMATIC,
                    {
                        "SERVER-PORT": 1,
                        "server_port": 2,
                        "database.password": SecretValue("s"),
                        "token": "x",
                    },
                )
            ],
        )
    assert duplicate.value.code == "config.duplicate_key"

    with pytest.raises(ConfigurationError) as source:
        build_config_snapshot(
            schema(),
            [
                ConfigSource(ConfigSourceKind.CLI, {}),
                ConfigSource(ConfigSourceKind.CLI, {}),
            ],
        )
    assert source.value.code == "config.duplicate_source"


def test_schema_version_and_required_field_fail_safely() -> None:
    with pytest.raises(ConfigurationError) as mismatch:
        build_config_snapshot(
            schema(), [ConfigSource(ConfigSourceKind.FILE, {}, schema_version=2)]
        )
    assert mismatch.value.code == "config.schema_mismatch"

    with pytest.raises(ConfigurationError) as missing:
        build_config_snapshot(schema())
    assert missing.value.code == "config.missing_required"


def test_snapshot_is_immutable_and_redacted() -> None:
    snapshot = build_config_snapshot(
        schema(),
        [secret_source()],
        secret_provider=Provider({"db/main": "super-secret"}),
    )
    with pytest.raises(TypeError):
        snapshot.values["server.port"] = 1  # type: ignore[index]
    assert snapshot.require("server.port", int) == 8000
    secret = snapshot.require("database.password", SecretValue)
    assert secret.reveal() == "super-secret"
    with pytest.raises(AttributeError):
        secret._value = "changed"  # type: ignore[misc]

    public = snapshot.redacted()
    assert public["server"]["port"] == 8000  # type: ignore[index]
    assert public["server"]["debug"] == "<internal>"  # type: ignore[index]
    assert public["database"]["password"] == "<secret>"  # type: ignore[index]
    assert public["token"] == "<sensitive>"
    internal = snapshot.redacted(include_internal=True)
    assert internal["server"]["debug"] is False  # type: ignore[index]


def test_plaintext_secret_never_enters_repr_or_revision_material() -> None:
    snapshot = build_config_snapshot(
        schema(),
        [secret_source()],
        secret_provider=Provider({"db/main": "super-secret"}),
    )
    rendered = (
        repr(snapshot) + repr(snapshot.redacted()) + snapshot.canonical_bytes.decode()
    )
    assert "super-secret" not in rendered
    assert "opaque-token" not in repr(snapshot.redacted())
    assert b"super-secret" not in snapshot.canonical_bytes
    assert b"db/main" not in snapshot.canonical_bytes
    assert b"opaque-token" not in snapshot.canonical_bytes


def test_revision_changes_for_nonsecret_values_but_not_plaintext_secret_rotation() -> (
    None
):
    source = [secret_source()]
    first = build_config_snapshot(
        schema(), source, secret_provider=Provider({"db/main": "a"})
    )
    rotated = build_config_snapshot(
        schema(), source, secret_provider=Provider({"db/main": "b"})
    )
    changed = build_config_snapshot(
        schema(),
        [
            ConfigSource(
                ConfigSourceKind.PROGRAMMATIC,
                {
                    "server.port": 9000,
                    "database.password": SecretRef("db/main"),
                    "token": "opaque-token",
                },
            )
        ],
        secret_provider=Provider({"db/main": "a"}),
    )
    assert first.revision_id == rotated.revision_id
    assert first.revision_id != changed.revision_id


def test_secret_contract_and_resolution_failure_are_safe() -> None:
    with pytest.raises(ConfigurationError) as plain:
        build_config_snapshot(
            schema(),
            [
                ConfigSource(
                    ConfigSourceKind.PROGRAMMATIC,
                    {"database.password": "plaintext", "token": "x"},
                )
            ],
        )
    assert plain.value.code == "config.secret_required"

    with pytest.raises(ConfigurationError) as missing_provider:
        build_config_snapshot(schema(), [secret_source()])
    assert missing_provider.value.code == "config.secret_provider_missing"

    class Failing:
        def resolve(self, reference: str) -> str:
            raise RuntimeError(f"secret leaked: {reference} /private/path")

    with pytest.raises(ConfigurationError) as failed:
        build_config_snapshot(schema(), [secret_source()], secret_provider=Failing())
    assert failed.value.code == "config.secret_resolution_failed"
    assert "private" not in str(failed.value)
    assert "db/main" not in str(failed.value)


def test_environment_source_is_string_only_and_never_evaluates() -> None:
    marker = "__import__('os').system('false')"
    source = environment_source(
        {"LINGSHU_SERVER__PORT": "9001", "LINGSHU_TOKEN": marker, "OTHER": "ignored"}
    )
    snapshot = build_config_snapshot(
        schema(),
        [
            source,
            ConfigSource(
                ConfigSourceKind.PROGRAMMATIC,
                {"database.password": SecretValue("s")},
            ),
        ],
    )
    assert snapshot["server.port"] == 9001
    assert snapshot["token"] == marker


def test_key_normalization_is_explicit() -> None:
    assert normalize_config_key(" Server-Mode.Debug ") == "server_mode.debug"
    with pytest.raises(ValueError):
        normalize_config_key("server..port")
