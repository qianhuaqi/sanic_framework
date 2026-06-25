import pytest

from framework.config import AppConfig, load_config, parse_bool, parse_csv, parse_host_port


def test_parse_bool_accepts_common_values():
    assert parse_bool("true") is True
    assert parse_bool("1") is True
    assert parse_bool("yes") is True
    assert parse_bool("false") is False
    assert parse_bool("0") is False
    assert parse_bool("no") is False
    assert parse_bool(False) is False


def test_parse_csv_trims_empty_values():
    assert parse_csv("mysql, redis,,mongo") == ["mysql", "redis", "mongo"]
    assert parse_csv("") == []


def test_parse_host_port_handles_defaults():
    assert parse_host_port("127.0.0.1:3307") == ("127.0.0.1", 3307)
    assert parse_host_port("127.0.0.1") == ("127.0.0.1", 3306)
    assert parse_host_port("") == ("localhost", 3306)


def test_load_config_defaults_disable_databases(monkeypatch):
    for key in (
        "APP_NAME",
        "PROJECT_NAME",
        "HOST",
        "PORT",
        "WORKERS",
        "DEBUG",
        "LANGUAGE",
        "MYSQL_ENABLED",
        "REDIS_ENABLED",
        "MONGO_ENABLED",
        "SQLITE_ENABLED",
        "ENABLE_AUTH",
        "ENABLE_SIGNING",
        "ENABLE_I18N",
        "ENABLE_RESPONSE_CACHE",
        "CORS_ENABLED",
        "CORS_ORIGINS",
        "CORS_ALLOW_METHODS",
        "CORS_ALLOW_HEADERS",
        "CORS_ALLOW_CREDENTIALS",
        "CORS_MAX_AGE",
        "LOG_TO_FILE",
        "LOG_LEVEL",
        "LOG_PATH",
        "LOG_FILE",
        "LOG_FORMATTER",
        "LOG_MAX_BYTES",
        "LOG_BACKUP_COUNT",
    ):
        monkeypatch.delenv(key, raising=False)
    config = load_config(load_env=False)
    assert isinstance(config, AppConfig)
    assert config.enabled_databases == []
    assert config.host == "0.0.0.0"
    assert config.port == 8000
    assert config.debug is False
    assert config.language == "zh-CN"
    assert config.mysql["mode"] == "single"
    assert config.mysql["slaves"] == []
    assert config.redis["mode"] == "single"
    assert config.redis["sentinels"] == []
    assert config.cors_enabled is False
    assert config.cors_origins == ["*"]
    assert config.cors_allow_methods == ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    assert config.log_to_file is False
    assert config.log_level == "INFO"
    assert config.log_path == "runtime/logs"
    assert config.log_file == "app.log"


def test_load_config_normalizes_language(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "zh")

    config = load_config()

    assert config.language == "zh-CN"


def test_load_config_reads_project_defaults_and_env_overrides(monkeypatch, tmp_path):
    defaults = tmp_path / "project_defaults.py"
    defaults.write_text(
        'APP_NAME = "from-config"\n'
        "PORT = 9100\n"
        "CORS_ENABLED = True\n"
        'CORS_ORIGINS = ["https://config.test"]\n',
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("PROJECT_CONFIG_MODULE", "project_defaults")
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    config = load_config(load_env=False)

    assert config.app_name == "from-config"
    assert config.port == 9100
    assert config.cors_enabled is True
    assert config.cors_origins == ["https://config.test"]

    monkeypatch.setenv("APP_NAME", "from-env")
    config = load_config(load_env=False)
    assert config.app_name == "from-env"


def test_load_config_with_single_switches(monkeypatch):
    for key in (
        "MYSQL_ENABLED",
        "REDIS_ENABLED",
        "MONGO_ENABLED",
        "SQLITE_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MYSQL_ENABLED", "true")
    monkeypatch.setenv("REDIS_ENABLED", "true")

    config = load_config()

    assert config.enabled_databases == ["mysql", "redis"]
    assert config.mysql_enabled is True
    assert config.redis_enabled is True
    assert config.mongo_enabled is False


def test_load_config_parses_cors(monkeypatch):
    monkeypatch.setenv("CORS_ENABLED", "true")
    monkeypatch.setenv("CORS_ORIGINS", "https://a.test,https://b.test")
    monkeypatch.setenv("CORS_ALLOW_METHODS", "GET,POST")
    monkeypatch.setenv("CORS_ALLOW_HEADERS", "Content-Type,Authorization")
    monkeypatch.setenv("CORS_ALLOW_CREDENTIALS", "true")
    monkeypatch.setenv("CORS_MAX_AGE", "600")

    config = load_config()

    assert config.cors_enabled is True
    assert config.cors_origins == ["https://a.test", "https://b.test"]
    assert config.cors_allow_methods == ["GET", "POST"]
    assert config.cors_allow_headers == ["Content-Type", "Authorization"]
    assert config.cors_allow_credentials is True
    assert config.cors_max_age == 600


def test_load_config_parses_logging(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_TO_FILE", "true")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_PATH", str(tmp_path / "logs"))
    monkeypatch.setenv("LOG_FILE", "demo.log")
    monkeypatch.setenv("LOG_FORMATTER", "%(levelname)s:%(message)s")
    monkeypatch.setenv("LOG_MAX_BYTES", "2048")
    monkeypatch.setenv("LOG_BACKUP_COUNT", "3")

    config = load_config()

    assert config.log_to_file is True
    assert config.log_level == "DEBUG"
    assert config.log_path == str(tmp_path / "logs")
    assert config.log_file == "demo.log"
    assert config.log_formatter == "%(levelname)s:%(message)s"
    assert config.log_max_bytes == 2048
    assert config.log_backup_count == 3


def test_load_config_parses_mysql_master_slave_and_redis_sentinel(monkeypatch):
    for key in (
        "MYSQL_ENABLED",
        "MYSQL_MASTER_HOST",
        "MYSQL_MASTER_PORT",
        "MYSQL_MASTER_USER",
        "MYSQL_MASTER_PASSWORD",
        "MYSQL_MASTER_DATABASE",
        "MYSQL_SLAVES",
        "REDIS_ENABLED",
        "REDIS_SENTINEL_ENABLED",
        "REDIS_SENTINELS",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("MYSQL_ENABLED", "true")
    monkeypatch.setenv("MYSQL_MASTER_HOST", "10.0.0.1")
    monkeypatch.setenv("MYSQL_MASTER_PORT", "3306")
    monkeypatch.setenv("MYSQL_MASTER_USER", "writer")
    monkeypatch.setenv("MYSQL_MASTER_PASSWORD", "secret")
    monkeypatch.setenv("MYSQL_MASTER_DATABASE", "demo")
    monkeypatch.setenv("MYSQL_SLAVES", "10.0.0.2:3307,10.0.0.3:3308")

    monkeypatch.setenv("REDIS_ENABLED", "true")
    monkeypatch.setenv("REDIS_SENTINEL_ENABLED", "true")
    monkeypatch.setenv("REDIS_SENTINELS", "10.0.0.4:26379,10.0.0.5:26379")

    config = load_config()

    assert config.mysql["mode"] == "master_slave"
    assert config.mysql["master"]["host"] == "10.0.0.1"
    assert config.mysql["master"]["user"] == "writer"
    assert config.mysql["slaves"] == [
        {"host": "10.0.0.2", "port": 3307, "user": "writer", "password": "secret", "database": "demo"},
        {"host": "10.0.0.3", "port": 3308, "user": "writer", "password": "secret", "database": "demo"},
    ]
    assert config.redis["mode"] == "sentinel"
    assert config.redis["sentinels"] == [("10.0.0.4", 26379), ("10.0.0.5", 26379)]


def test_load_config_rejects_legacy_enabled_databases(monkeypatch):
    monkeypatch.setenv("ENABLED_DATABASES", "mysql,redis")
    with pytest.raises(RuntimeError, match="ENABLED_DATABASES is no longer supported"):
        load_config()


def test_load_config_rejects_sqlite_as_unimplemented(monkeypatch):
    monkeypatch.setenv("SQLITE_ENABLED", "true")
    with pytest.raises(RuntimeError, match="SQLite support is not implemented"):
        load_config()
