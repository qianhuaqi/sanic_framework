from lingshu.extensions.registry import setup_enabled_extensions, teardown_enabled_extensions
from lingshu.system.lifecycle import ApplicationLifecycle, ShutdownCoordinator, install_health_routes


def register_lifecycle(app, extension_modules=None):
    extension_modules = list(extension_modules or [])
    lifecycle = getattr(app.ctx, "lifecycle", None)
    if lifecycle is None:
        lifecycle = ApplicationLifecycle()
        app.ctx.lifecycle = lifecycle
    app.ctx.shutdown_coordinator = ShutdownCoordinator(lifecycle, shutdown_timeout=25.0, cleanup_timeout=8.0)
    install_health_routes(app, lifecycle)

    @app.listener("before_server_start")
    async def setup_extensions(app):
        await setup_enabled_extensions(app, extension_modules)
        if lifecycle.state.value == "starting":
            lifecycle.mark_ready()

    @app.listener("after_server_stop")
    async def teardown_extensions(app):
        await teardown_enabled_extensions(app, extension_modules)
