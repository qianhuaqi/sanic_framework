from lingshu.database.redis import RedisManager
from lingshu.system import sanic_adapter


async def setup(app):
    config = sanic_adapter.get_app_config(app)
    if "redis" not in config.enabled_databases:
        return
    redis = RedisManager(config.redis)
    sanic_adapter.set_resource(app, "redis", redis)
    await redis.connect()


async def teardown(app):
    redis = sanic_adapter.get_optional_resource(app, "redis")
    close = getattr(redis, "close", None)
    if close:
        await close()
