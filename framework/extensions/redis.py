from framework.database.redis import RedisManager


async def setup(app):
    if "redis" not in app.ctx.config.enabled_databases:
        return
    app.ctx.redis = RedisManager(app.ctx.config.redis)
    await app.ctx.redis.connect()


async def teardown(app):
    redis = getattr(app.ctx, "redis", None)
    close = getattr(redis, "close", None)
    if close:
        await close()
