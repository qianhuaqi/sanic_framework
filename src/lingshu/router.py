from dataclasses import dataclass

from lingshu.system.policy import RoutePolicyCompiler, RoutePolicyDefinition, RoutePolicyRegistry


@dataclass(frozen=True)
class RoutePolicy:
    auth_required: bool = True
    signing_required: bool = False
    maintenance_check: bool = True
    tenant_required: bool = False


def set_blueprint_policy(blueprint, policy: RoutePolicy):
    blueprint.ctx.route_policy = policy
    return blueprint


def get_blueprint_policy(blueprint) -> RoutePolicy:
    return getattr(blueprint.ctx, "route_policy", RoutePolicy())


def register_blueprints(app, blueprints):
    for blueprint in blueprints:
        app.blueprint(blueprint)


def compile_route_policies(app, defaults: RoutePolicyDefinition | None = None):
    compiled = RoutePolicyCompiler(RoutePolicyRegistry(defaults=defaults)).compile_app(app)
    app.ctx.route_policies = compiled
    return compiled
