from lingshu.router import RoutePolicy, get_blueprint_policy
from app.controller.health import bp


def test_route_policy_defaults_are_protective():
    policy = RoutePolicy()
    assert policy.auth_required is True
    assert policy.signing_required is False
    assert policy.maintenance_check is True


def test_health_blueprint_policy_is_public():
    policy = get_blueprint_policy(bp)
    assert policy.auth_required is False
    assert policy.signing_required is False
    assert policy.maintenance_check is False
