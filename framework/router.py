from dataclasses import dataclass


@dataclass(frozen=True)
class RoutePolicy:
    auth_required: bool = True
    signing_required: bool = False
    maintenance_check: bool = True


def set_blueprint_policy(blueprint, policy: RoutePolicy):
    blueprint.ctx.route_policy = policy
    return blueprint


def get_blueprint_policy(blueprint) -> RoutePolicy:
    return getattr(blueprint.ctx, "route_policy", RoutePolicy())


def register_blueprints(app, blueprints):
    for blueprint in blueprints:
        app.blueprint(blueprint)
