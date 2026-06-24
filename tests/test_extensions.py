import pytest

from framework.app import create_app
from framework.extensions.registry import is_database_enabled, require_database


def test_no_database_enabled_by_default():
    app = create_app()
    assert is_database_enabled(app, "mysql") is False
    assert is_database_enabled(app, "redis") is False
    assert is_database_enabled(app, "mongo") is False


def test_require_database_raises_clear_error():
    app = create_app()
    with pytest.raises(RuntimeError, match="Database 'mysql' is not enabled"):
        require_database(app, "mysql")
