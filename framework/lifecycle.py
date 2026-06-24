from framework.extensions.registry import setup_enabled_extensions, teardown_enabled_extensions


def register_lifecycle(app, extension_modules=None):
    extension_modules = list(extension_modules or [])
    @app.listener("before_server_start")
    async def setup_extensions(app):
        await setup_enabled_extensions(app, extension_modules)

    @app.listener("after_server_stop")
    async def teardown_extensions(app):
        await teardown_enabled_extensions(app, extension_modules)
