async def setup(app):
    if "mongo" not in app.ctx.config.enabled_databases:
        return
    from framework.database.mongo import MongoDB

    app.ctx.mongo = MongoDB(app.ctx.config.mongo)
    await app.ctx.mongo.connect()


async def teardown(app):
    mongo = getattr(app.ctx, "mongo", None)
    disconnect = getattr(mongo, "disconnect", None)
    if disconnect:
        await disconnect()
