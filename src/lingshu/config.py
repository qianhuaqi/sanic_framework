from collections.abc import Iterable
from dataclasses import dataclass
from importlib import import_module
import os
from types import MappingProxyType
from types import ModuleType

from dotenv import load_dotenv

from lingshu.error_codes import normalize_locale_name


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off", ""}
SUPPORTED_DATABASES = ("mysql", "redis", "mongo", "sqlite")
IMPLEMENTED_DATABASES = {"mysql", "redis", "mongo"}


def project_setting(name: str, default=None):
    module_name = os.getenv("PROJECT_CONFIG_MODULE", "config.defaults")
    try:
        module = import_module(module_name)
    except ImportError:
        return default
    return getattr(module, name, default)


def env_or_setting(name: str, default=None):
    return os.getenv(name, project_setting(name, default))


def parse_bool(value):
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


def parse_csv(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, Iterable) and not isinstance(value, str):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def normalize_database_name(name: str) -> str:
    return str(name).strip().lower().replace("-", "_")


def parse_host_port(value: str, default_host: str = "localhost", default_port: int = 3306) -> tuple[str, int]:
    text = str(value).strip()
    if not text:
        return default_host, default_port
    if ":" not in text:
        return text, default_port
    host, port_text = text.rsplit(":", 1)
    return host.strip() or default_host, int(port_text.strip() or default_port)


def parse_host_port_list(value: str, default_port: int = 3306) -> list[tuple[str, int]]:
    return [parse_host_port(item, default_port=default_port) for item in parse_csv(value)]


def build_mysql_endpoint(prefix: str, defaults: dict[str, object]) -> dict[str, object]:
    return {
        "host": env_or_setting(f"{prefix}_HOST", defaults.get("host", "localhost")),
        "port": int(env_or_setting(f"{prefix}_PORT", defaults.get("port", 3306))),
        "user": env_or_setting(f"{prefix}_USER", defaults.get("user", "")),
        "password": env_or_setting(f"{prefix}_PASSWORD", defaults.get("password", "")),
        "database": env_or_setting(f"{prefix}_DATABASE", defaults.get("database", "")),
    }


def build_mysql_config() -> dict:
    master = build_mysql_endpoint(
        "MYSQL_MASTER",
        {
            "host": env_or_setting("MYSQL_HOST", "localhost"),
            "port": int(env_or_setting("MYSQL_PORT", "3306")),
            "user": env_or_setting("MYSQL_USER", ""),
            "password": env_or_setting("MYSQL_PASSWORD", ""),
            "database": env_or_setting("MYSQL_DATABASE", ""),
        },
    )
    slaves = [
        {
            **master,
            "host": host,
            "port": port,
        }
        for host, port in parse_host_port_list(env_or_setting("MYSQL_SLAVES", ""), default_port=master["port"])
    ]
    return {
        "enabled": parse_bool(env_or_setting("MYSQL_ENABLED", "false")),
        "mode": "master_slave" if slaves else "single",
        "master": master,
        "slaves": slaves,
        "pool_size": int(env_or_setting("MYSQL_POOL_SIZE", "5")),
        "pool_recycle": int(env_or_setting("MYSQL_POOL_RECYCLE", "3600")),
    }


def build_redis_config() -> dict:
    sentinel_enabled = parse_bool(env_or_setting("REDIS_SENTINEL_ENABLED", "false"))
    sentinels = parse_host_port_list(env_or_setting("REDIS_SENTINELS", ""), default_port=26379)
    if sentinel_enabled and not sentinels:
        raise ValueError("REDIS_SENTINEL_ENABLED=true requires REDIS_SENTINELS to be configured")
    return {
        "enabled": parse_bool(env_or_setting("REDIS_ENABLED", "false")),
        "mode": "sentinel" if sentinel_enabled else "single",
        "host": env_or_setting("REDIS_HOST", "localhost"),
        "port": int(env_or_setting("REDIS_PORT", "6379")),
        "password": env_or_setting("REDIS_PASSWORD", ""),
        "db": int(env_or_setting("REDIS_DB", "0")),
        "expire": int(env_or_setting("REDIS_EXPIRE", "3600")),
        "prefix": env_or_setting("REDIS_PREFIX", "sanic_"),
        "idle_timeout": int(env_or_setting("REDIS_IDLE_TIMEOUT", "600")),
        "sentinel_enabled": sentinel_enabled,
        "sentinels": sentinels,
        "master_name": env_or_setting("REDIS_MASTER_NAME", "mymaster"),
    }


def build_mongo_config() -> dict:
    return {
        "enabled": parse_bool(env_or_setting("MONGO_ENABLED", "false")),
        "host": env_or_setting("MONGODB_HOST", "localhost"),
        "port": int(env_or_setting("MONGODB_PORT", "27017")),
        "username": env_or_setting("MONGODB_USERNAME", ""),
        "password": env_or_setting("MONGODB_PASSWORD", ""),
        "database": env_or_setting("MONGODB_DATABASE", ""),
    }


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    project_name: str
    host: str
    port: int
    workers: int
    debug: bool
    language: str
    enabled_databases: list[str]
    mysql_enabled: bool
    redis_enabled: bool
    mongo_enabled: bool
    sqlite_enabled: bool
    enable_auth: bool
    enable_signing: bool
    enable_i18n: bool
    enable_response_cache: bool
    auth_secret: str
    auth_app: int
    auth_expire: int
    cors_enabled: bool
    cors_origins: list[str]
    cors_allow_methods: list[str]
    cors_allow_headers: list[str]
    cors_allow_credentials: bool
    cors_max_age: int
    auth_white_ip_list: list[str]
    signing_secret: str
    log_to_file: bool
    log_level: str
    log_path: str
    log_file: str
    log_formatter: str
    log_max_bytes: int
    log_backup_count: int
    crypt_response_enabled: bool
    crypt_response_secret: str
    crypt_params_secret: str
    mysql: dict
    redis: dict
    mongo: dict

    @property
    def auth(self) -> dict[str, object]:
        return {
            "secret": self.auth_secret,
            "app": self.auth_app,
            "expire": self.auth_expire,
        }


def load_config(env_file: str | None = None, load_env: bool = True) -> AppConfig:
    if env_file:
        load_dotenv(env_file, override=True)
    elif load_env and os.getenv("SANIC_ENV", "").lower() not in {"test", "testing"}:
        load_dotenv()

    legacy_databases = parse_csv(env_or_setting("ENABLED_DATABASES", ""))
    if legacy_databases:
        raise RuntimeError(
            "ENABLED_DATABASES is no longer supported; use MYSQL_ENABLED, REDIS_ENABLED, MONGO_ENABLED, or SQLITE_ENABLED"
        )

    mysql_enabled = parse_bool(env_or_setting("MYSQL_ENABLED", "false"))
    redis_enabled = parse_bool(env_or_setting("REDIS_ENABLED", "false"))
    mongo_enabled = parse_bool(env_or_setting("MONGO_ENABLED", "false"))
    sqlite_enabled = parse_bool(env_or_setting("SQLITE_ENABLED", "false"))

    if sqlite_enabled:
        raise RuntimeError("SQLite support is not implemented in this template yet")

    enabled_databases = [
        name for name, enabled in (
            ("mysql", mysql_enabled),
            ("redis", redis_enabled),
            ("mongo", mongo_enabled),
        )
        if enabled
    ]

    return AppConfig(
        app_name=env_or_setting("APP_NAME", "sanic-template"),
        project_name=env_or_setting("PROJECT_NAME", "sanic-template"),
        host=env_or_setting("HOST", "0.0.0.0"),
        port=int(env_or_setting("PORT", "8000")),
        workers=int(env_or_setting("WORKERS", "1")),
        debug=parse_bool(env_or_setting("DEBUG", "false")),
        language=normalize_locale_name(env_or_setting("LANGUAGE", "zh-CN")),
        enabled_databases=enabled_databases,
        mysql_enabled=mysql_enabled,
        redis_enabled=redis_enabled,
        mongo_enabled=mongo_enabled,
        sqlite_enabled=sqlite_enabled,
        enable_auth=parse_bool(env_or_setting("ENABLE_AUTH", "true")),
        enable_signing=parse_bool(env_or_setting("ENABLE_SIGNING", "true")),
        enable_i18n=parse_bool(env_or_setting("ENABLE_I18N", "true")),
        enable_response_cache=parse_bool(env_or_setting("ENABLE_RESPONSE_CACHE", "true")),
        auth_secret=env_or_setting("AUTH_SECRET", "change-me"),
        auth_app=int(env_or_setting("AUTH_APP", "1")),
        auth_expire=int(env_or_setting("AUTH_EXPIRE", "7200")),
        cors_enabled=parse_bool(env_or_setting("CORS_ENABLED", "false")),
        cors_origins=parse_csv(env_or_setting("CORS_ORIGINS", "*")),
        cors_allow_methods=parse_csv(env_or_setting("CORS_ALLOW_METHODS", "GET,POST,PUT,PATCH,DELETE,OPTIONS")),
        cors_allow_headers=parse_csv(env_or_setting("CORS_ALLOW_HEADERS", "Content-Type,Authorization,X-Request-ID")),
        cors_allow_credentials=parse_bool(env_or_setting("CORS_ALLOW_CREDENTIALS", "false")),
        cors_max_age=int(env_or_setting("CORS_MAX_AGE", "86400")),
        auth_white_ip_list=parse_csv(env_or_setting("AUTH_WHITE_IP_LIST", "")),
        signing_secret=env_or_setting("SIGNING_SECRET", "change-me"),
        log_to_file=parse_bool(env_or_setting("LOG_TO_FILE", "false")),
        log_level=str(env_or_setting("LOG_LEVEL", "DEBUG" if parse_bool(env_or_setting("DEBUG", "false")) else "INFO")),
        log_path=env_or_setting("LOG_PATH", "runtime/logs"),
        log_file=env_or_setting("LOG_FILE", "app.log"),
        log_formatter=env_or_setting(
            "LOG_FORMATTER",
            "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        ),
        log_max_bytes=int(env_or_setting("LOG_MAX_BYTES", "10485760")),
        log_backup_count=int(env_or_setting("LOG_BACKUP_COUNT", "7")),
        crypt_response_enabled=parse_bool(env_or_setting("CRYPT_RESPONSE_ENABLED", "false")),
        crypt_response_secret=env_or_setting("CRYPT_RESPONSE_SECRET", "change-me"),
        crypt_params_secret=env_or_setting("CRYPT_PARAMS_SECRET", "change-me"),
        mysql=build_mysql_config(),
        redis=build_redis_config(),
        mongo=build_mongo_config(),
    )


def _freeze_value(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_value(item) for item in value)
    return value


class _ConfigModule(ModuleType):
    def _facade_config(self):
        from lingshu.system.context import get_current_app
        from lingshu.system.sanic_adapter import get_app_config

        return get_app_config(get_current_app())

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _freeze_value(getattr(self._facade_config(), name))

    def __getitem__(self, key):
        return _freeze_value(getattr(self._facade_config(), str(key).lower()))

    def __setattr__(self, name, value):
        if name.startswith("_"):
            return super().__setattr__(name, value)
        raise AttributeError("LingShu config facade is read-only")


def _install_module_facade():
    import sys

    sys.modules[__name__].__class__ = _ConfigModule


_install_module_facade()
