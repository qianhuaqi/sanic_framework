from collections.abc import Iterable
from dataclasses import dataclass
import os

from dotenv import load_dotenv

from framework.error_codes import normalize_locale_name


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off", ""}
SUPPORTED_DATABASES = ("mysql", "redis", "mongo", "sqlite")
IMPLEMENTED_DATABASES = {"mysql", "redis", "mongo"}


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
        "host": os.getenv(f"{prefix}_HOST", str(defaults.get("host", "localhost"))),
        "port": int(os.getenv(f"{prefix}_PORT", str(defaults.get("port", 3306)))),
        "user": os.getenv(f"{prefix}_USER", str(defaults.get("user", ""))),
        "password": os.getenv(f"{prefix}_PASSWORD", str(defaults.get("password", ""))),
        "database": os.getenv(f"{prefix}_DATABASE", str(defaults.get("database", ""))),
    }


def build_mysql_config() -> dict:
    master = build_mysql_endpoint(
        "MYSQL_MASTER",
        {
            "host": os.getenv("MYSQL_HOST", "localhost"),
            "port": int(os.getenv("MYSQL_PORT", "3306")),
            "user": os.getenv("MYSQL_USER", ""),
            "password": os.getenv("MYSQL_PASSWORD", ""),
            "database": os.getenv("MYSQL_DATABASE", ""),
        },
    )
    slaves = [
        {
            **master,
            "host": host,
            "port": port,
        }
        for host, port in parse_host_port_list(os.getenv("MYSQL_SLAVES", ""), default_port=master["port"])
    ]
    return {
        "enabled": parse_bool(os.getenv("MYSQL_ENABLED", "false")),
        "mode": "master_slave" if slaves else "single",
        "master": master,
        "slaves": slaves,
        "pool_size": int(os.getenv("MYSQL_POOL_SIZE", "5")),
        "pool_recycle": int(os.getenv("MYSQL_POOL_RECYCLE", "3600")),
    }


def build_redis_config() -> dict:
    sentinel_enabled = parse_bool(os.getenv("REDIS_SENTINEL_ENABLED", "false"))
    sentinels = parse_host_port_list(os.getenv("REDIS_SENTINELS", ""), default_port=26379)
    if sentinel_enabled and not sentinels:
        raise ValueError("REDIS_SENTINEL_ENABLED=true requires REDIS_SENTINELS to be configured")
    return {
        "enabled": parse_bool(os.getenv("REDIS_ENABLED", "false")),
        "mode": "sentinel" if sentinel_enabled else "single",
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", "6379")),
        "password": os.getenv("REDIS_PASSWORD", ""),
        "db": int(os.getenv("REDIS_DB", "0")),
        "expire": int(os.getenv("REDIS_EXPIRE", "3600")),
        "prefix": os.getenv("REDIS_PREFIX", "sanic_"),
        "idle_timeout": int(os.getenv("REDIS_IDLE_TIMEOUT", "600")),
        "sentinel_enabled": sentinel_enabled,
        "sentinels": sentinels,
        "master_name": os.getenv("REDIS_MASTER_NAME", "mymaster"),
    }


def build_mongo_config() -> dict:
    return {
        "enabled": parse_bool(os.getenv("MONGO_ENABLED", "false")),
        "host": os.getenv("MONGODB_HOST", "localhost"),
        "port": int(os.getenv("MONGODB_PORT", "27017")),
        "username": os.getenv("MONGODB_USERNAME", ""),
        "password": os.getenv("MONGODB_PASSWORD", ""),
        "database": os.getenv("MONGODB_DATABASE", ""),
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
    cors_enabled: bool
    cors_origins: list[str]
    cors_allow_methods: list[str]
    cors_allow_headers: list[str]
    cors_allow_credentials: bool
    cors_max_age: int
    auth_white_ip_list: list[str]
    signing_secret: str
    mysql: dict
    redis: dict
    mongo: dict


def load_config(env_file: str | None = None, load_env: bool = True) -> AppConfig:
    if env_file:
        load_dotenv(env_file, override=True)
    elif load_env and os.getenv("SANIC_ENV", "").lower() not in {"test", "testing"}:
        load_dotenv()

    legacy_databases = parse_csv(os.getenv("ENABLED_DATABASES", ""))
    if legacy_databases:
        raise RuntimeError(
            "ENABLED_DATABASES is no longer supported; use MYSQL_ENABLED, REDIS_ENABLED, MONGO_ENABLED, or SQLITE_ENABLED"
        )

    mysql_enabled = parse_bool(os.getenv("MYSQL_ENABLED", "false"))
    redis_enabled = parse_bool(os.getenv("REDIS_ENABLED", "false"))
    mongo_enabled = parse_bool(os.getenv("MONGO_ENABLED", "false"))
    sqlite_enabled = parse_bool(os.getenv("SQLITE_ENABLED", "false"))

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
        app_name=os.getenv("APP_NAME", "sanic-template"),
        project_name=os.getenv("PROJECT_NAME", "sanic-template"),
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        workers=int(os.getenv("WORKERS", "1")),
        debug=parse_bool(os.getenv("DEBUG", "false")),
        language=normalize_locale_name(os.getenv("LANGUAGE", "zh-CN")),
        enabled_databases=enabled_databases,
        mysql_enabled=mysql_enabled,
        redis_enabled=redis_enabled,
        mongo_enabled=mongo_enabled,
        sqlite_enabled=sqlite_enabled,
        enable_auth=parse_bool(os.getenv("ENABLE_AUTH", "true")),
        enable_signing=parse_bool(os.getenv("ENABLE_SIGNING", "true")),
        enable_i18n=parse_bool(os.getenv("ENABLE_I18N", "true")),
        enable_response_cache=parse_bool(os.getenv("ENABLE_RESPONSE_CACHE", "true")),
        cors_enabled=parse_bool(os.getenv("CORS_ENABLED", "false")),
        cors_origins=parse_csv(os.getenv("CORS_ORIGINS", "*")),
        cors_allow_methods=parse_csv(os.getenv("CORS_ALLOW_METHODS", "GET,POST,PUT,PATCH,DELETE,OPTIONS")),
        cors_allow_headers=parse_csv(os.getenv("CORS_ALLOW_HEADERS", "Content-Type,Authorization,X-Request-ID")),
        cors_allow_credentials=parse_bool(os.getenv("CORS_ALLOW_CREDENTIALS", "false")),
        cors_max_age=int(os.getenv("CORS_MAX_AGE", "86400")),
        auth_white_ip_list=parse_csv(os.getenv("AUTH_WHITE_IP_LIST", "")),
        signing_secret=os.getenv("SIGNING_SECRET", "change-me"),
        mysql=build_mysql_config(),
        redis=build_redis_config(),
        mongo=build_mongo_config(),
    )
