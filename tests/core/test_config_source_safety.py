from __future__ import annotations

import pytest
from lingshu.core import ConfigSource, ConfigSourceKind


def test_config_source_defensively_freezes_caller_mapping() -> None:
    caller_values = {"server": {"port": 8000}, "features": ["base"]}
    source = ConfigSource(ConfigSourceKind.CLI, caller_values)

    caller_values["server"]["port"] = 9000  # type: ignore[index]
    caller_values["features"] = ["changed"]

    server = source.values["server"]
    assert server["port"] == 8000  # type: ignore[index]
    assert source.values["features"] == ("base",)
    with pytest.raises(TypeError):
        source.values["server"] = {}  # type: ignore[index]
