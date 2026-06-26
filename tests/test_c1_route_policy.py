from dataclasses import FrozenInstanceError

import pytest
from sanic import Blueprint, Sanic

from lingshu.router import RoutePolicy, set_blueprint_policy
from lingshu.system.policy import (
    CompiledRoutePolicy,
    RoutePolicyCompiler,
    RoutePolicyDefinition,
    RoutePolicyError,
    RoutePolicyRegistry,
    set_route_policy,
)


def test_route_policy_compiler_applies_global_blueprint_route_precedence():
    app = Sanic("policy-precedence")
    bp = Blueprint("v1", url_prefix="/v1")
    set_blueprint_policy(bp, RoutePolicyDefinition(public=True, auth_required=False, timeout=5.0))

    @bp.get("/items", name="items")
    async def items(request):
        return None

    set_route_policy(items, RoutePolicyDefinition(timeout=1.5, audit_level="metadata"))
    app.blueprint(bp)

    registry = RoutePolicyRegistry(defaults=RoutePolicyDefinition(timeout=10.0))
    compiled = RoutePolicyCompiler(registry).compile_app(app)
    policy = compiled.for_route("v1.items")

    assert isinstance(policy, CompiledRoutePolicy)
    assert policy.public is True
    assert policy.auth_required is False
    assert policy.timeout == 1.5
    assert policy.audit_level == "metadata"
    with pytest.raises(FrozenInstanceError):
        policy.timeout = 9.0


def test_route_policy_compiler_rejects_invalid_timeout_and_public_auth_conflict():
    with pytest.raises(RoutePolicyError, match="timeout"):
        RoutePolicyDefinition(timeout=0)

    with pytest.raises(RoutePolicyError, match="public.*auth_required"):
        RoutePolicyDefinition(public=True, auth_required=True)


def test_route_policy_compiler_rejects_unknown_fields():
    with pytest.raises(RoutePolicyError, match="unknown"):
        RoutePolicyDefinition.from_mapping({"timeout": 1.0, "jwt": "later-phase"})


def test_every_route_receives_compiled_policy():
    app = Sanic("policy-all-routes")

    @app.get("/a", name="a")
    async def a(request):
        return None

    @app.post("/b", name="b")
    async def b(request):
        return None

    compiled = RoutePolicyCompiler(RoutePolicyRegistry()).compile_app(app)

    assert compiled.for_route("a").route_name == "a"
    assert compiled.for_route("b").route_name == "b"


def test_legacy_route_policy_is_compatible_with_definition():
    policy = RoutePolicy(auth_required=False, signing_required=False, maintenance_check=False)
    definition = RoutePolicyDefinition.from_legacy(policy)

    assert definition.public is True
    assert definition.auth_required is False
    assert definition.maintenance_check is False
