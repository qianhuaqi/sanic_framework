async def setup(app):
    if "mysql" not in app.ctx.config.enabled_databases:
        return
    from framework.database.mysql import MySQLDatabase

    app.ctx.mysql = MySQLDatabase(app.ctx.config.mysql)
    await app.ctx.mysql.connect()


async def teardown(app):
    db = getattr(app.ctx, "mysql", None)
    disconnect = getattr(db, "disconnect", None)
    if disconnect:
        await disconnect()
