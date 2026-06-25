from lingshu.system import sanic_adapter


async def setup(app):
    config = sanic_adapter.get_app_config(app)
    if "mysql" not in config.enabled_databases:
        return
    from lingshu.database.mysql import MySQLDatabase

    mysql = MySQLDatabase(config.mysql)
    sanic_adapter.set_resource(app, "mysql", mysql)
    await mysql.connect()


async def teardown(app):
    db = sanic_adapter.get_optional_resource(app, "mysql")
    disconnect = getattr(db, "disconnect", None)
    if disconnect:
        await disconnect()
