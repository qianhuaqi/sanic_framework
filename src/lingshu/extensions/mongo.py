from lingshu.system import sanic_adapter


async def setup(app):
    config = sanic_adapter.get_app_config(app)
    if "mongo" not in config.enabled_databases:
        return
    from lingshu.database.mongo import MongoDB

    mongo = MongoDB(config.mongo)
    sanic_adapter.set_resource(app, "mongo", mongo)
    await mongo.connect()


async def teardown(app):
    mongo = sanic_adapter.get_optional_resource(app, "mongo")
    disconnect = getattr(mongo, "disconnect", None)
    if disconnect:
        await disconnect()
