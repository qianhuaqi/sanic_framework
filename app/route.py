import os


def _is_dev_or_test(config=None) -> bool:
    environment = os.getenv("SANIC_ENV", "development").lower()
    enabled = environment in {"development", "dev", "test", "testing"}
    if config is not None:
        enabled = enabled or bool(getattr(config, "debug", False))
    return enabled


def get_blueprints(config=None):
    from app.controller.health import bp as health_bp
    from app.v1.controller.demo import bp as demo_bp

    blueprints = [health_bp, demo_bp]
    if _is_dev_or_test(config):
        from app.controller.meta import bp as meta_bp

        blueprints.append(meta_bp)
    return blueprints
