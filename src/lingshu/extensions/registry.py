from lingshu.system import sanic_adapter


SUPPORTED_DATABASES = {"mysql", "redis", "mongo", "sqlite"}


def normalize_extension_name(name: str) -> str:
    return name.strip().lower().replace("-", "_")


def is_database_enabled(app, name: str) -> bool:
    normalized = normalize_extension_name(name)
    if normalized not in SUPPORTED_DATABASES:
        return False
    config = sanic_adapter.get_app_config(app)
    flag_name = f"{normalized}_enabled"
    if hasattr(config, flag_name):
        return bool(getattr(config, flag_name))
    return normalized in set(config.enabled_databases)


def require_database(app, name: str):
    normalized = normalize_extension_name(name)
    if normalized not in SUPPORTED_DATABASES:
        raise RuntimeError(f"Database '{name}' is not recognized")
    if normalized == "sqlite":
        raise RuntimeError("SQLite support is not implemented in this template yet")
    if not is_database_enabled(app, normalized):
        raise RuntimeError(f"Database '{name}' is not enabled for this project")
    return sanic_adapter.get_resource(app, name)


async def setup_enabled_extensions(app, extension_modules):
    for extension in extension_modules:
        setup = getattr(extension, "setup", None)
        if setup:
            await setup(app)


async def teardown_enabled_extensions(app, extension_modules):
    for extension in reversed(extension_modules):
        teardown = getattr(extension, "teardown", None)
        if teardown:
            await teardown(app)
