from framework.database.mysql import MySQLDatabase


async def setup(app):
    if "mysql" not in app.ctx.config.enabled_databases:
        return
    app.ctx.mysql = MySQLDatabase(app.ctx.config.mysql)
    await app.ctx.mysql.connect()


async def teardown(app):
    db = getattr(app.ctx, "mysql", None)
    disconnect = getattr(db, "disconnect", None)
    if disconnect:
        await disconnect()
