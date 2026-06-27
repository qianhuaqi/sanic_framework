"""Phase C2.2A tenant context and resolution tests.

Covers:
1. TenantContext immutability and validation.
2. TenantResolutionResult taxonomy and outcome.
3. TenantResolverChain ordering and short-circuit.
4. ClaimTenantResolver reference implementation.
5. StubTenantResolver.
6. RoutePolicy tenant_required compilation.
7. Fail-closed middleware (403).
8. request.tenant semantics.
9. Cleanup lifecycle (normal/exception/cancel).
10. Concurrent isolation.
11. Multi-app isolation.
12. Idempotent middleware / configure.
13. Import order stability.
14. No leakage in responses, repr, exceptions.
"""

from __future__ import annotations

import asyncio
from types import MappingProxyType, SimpleNamespace

import pytest
from sanic import Blueprint, Sanic

from lingshu.router import compile_route_policies
from lingshu.system.auth.principal import Principal
from lingshu.system.auth.tenant.context import TenantContext
from lingshu.system.auth.tenant.result import (
    TenantResolutionOutcome,
    TenantResolutionResult,
)
from lingshu.system.auth.tenant.resolver import TenantResolver, TenantResolverChain
from lingshu.system.auth.tenant.claim_resolver import ClaimTenantResolver
from lingshu.system.auth.tenant.stub_resolver import StubTenantResolver
from lingshu.system.auth.tenant.binding import (
    bind_tenant,
    current_tenant,
    require_tenant,
    tenant_scope,
)
from lingshu.system.auth.stub_authenticator import StubAuthenticator
from lingshu.system.auth.authenticator import AuthenticatorChain
from lingshu.system.errors import NoRequestContextError
from lingshu.system.policy import RoutePolicyDefinition, set_route_policy


_TEST_SECRET = "test-secret-key-at-least-32-bytes-long"


def _run(coro):
    return asyncio.run(coro)


def _make_authed_tenant_app(name, auth_chain=None, tenant_chain=None, tenant_required_routes=None):
    from lingshu.system import sanic_adapter
    from lingshu.system.auth.middleware import (
        install_authentication_middleware,
        set_authenticator_chain,
    )
    from lingshu.system.auth.tenant.middleware import (
        install_tenant_middleware,
        set_tenant_resolver_chain,
    )

    app = Sanic(name)
    sanic_adapter.install_context_middleware(app)

    bp = Blueprint(f"{name}-bp", url_prefix=f"/{name}")

    @bp.get("/public", name="public")
    async def public_handler(request):
        from lingshu.response import json_response
        return json_response({"ok": True})

    set_route_policy(public_handler, RoutePolicyDefinition(public=True))

    @bp.get("/protected", name="protected")
    async def protected_handler(request):
        from lingshu.response import json_response
        p = SimpleNamespace()
        from lingshu.system.auth.context import current_principal
        principal = current_principal.get()
        return json_response({"subject": principal.subject if principal else None})

    set_route_policy(protected_handler, RoutePolicyDefinition())

    @bp.get("/tenant", name="tenant")
    async def tenant_handler(request):
        from lingshu.response import json_response
        t = current_tenant.get()
        return json_response({"tenant_id": t.tenant_id if t else None})

    tr = True
    if tenant_required_routes and "tenant" not in tenant_required_routes:
        tr = False
    set_route_policy(tenant_handler, RoutePolicyDefinition(tenant_required=tr))

    app.blueprint(bp)
    compile_route_policies(app)

    if auth_chain is not None:
        set_authenticator_chain(app, auth_chain)
    if tenant_chain is not None:
        set_tenant_resolver_chain(app, tenant_chain)
    install_authentication_middleware(app)
    install_tenant_middleware(app)
    return app


# ---------------------------------------------------------------------------
# 1. TenantContext
# ---------------------------------------------------------------------------

class TestTenantContext:
    def test_create_defaults(self):
        ctx = TenantContext.create("t-1", "claim")
        assert ctx.tenant_id == "t-1"
        assert ctx.resolver_id == "claim"
        assert isinstance(ctx.attributes, MappingProxyType)
        assert len(ctx.attributes) == 0

    def test_create_with_attributes(self):
        ctx = TenantContext.create("t-1", "claim", attributes={"region": "us-east"})
        assert ctx.attributes["region"] == "us-east"

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            TenantContext.create("", "claim")

    def test_empty_resolver_id_rejected(self):
        with pytest.raises(ValueError):
            TenantContext.create("t-1", "")

    def test_is_frozen(self):
        ctx = TenantContext.create("t-1", "claim")
        with pytest.raises(Exception):
            ctx.tenant_id = "other"  # type: ignore[misc]

    def test_attributes_read_only(self):
        ctx = TenantContext.create("t-1", "claim", attributes={"k": "v"})
        with pytest.raises(TypeError):
            ctx.attributes["k"] = "other"  # type: ignore[index]

    def test_nested_dict_frozen(self):
        ctx = TenantContext.create("t", "r", attributes={"meta": {"role": "admin"}})
        with pytest.raises(TypeError):
            ctx.attributes["meta"]["role"] = "x"  # type: ignore[index]

    def test_nested_list_frozen(self):
        ctx = TenantContext.create("t", "r", attributes={"items": ["a", "b"]})
        assert isinstance(ctx.attributes["items"], tuple)

    def test_nested_set_frozen(self):
        ctx = TenantContext.create("t", "r", attributes={"perms": {"read", "write"}})
        assert isinstance(ctx.attributes["perms"], frozenset)

    def test_deeply_nested_frozen(self):
        ctx = TenantContext.create("t", "r", attributes={"l1": {"l2": {"l3": ["x"]}}})
        deep = ctx.attributes["l1"]["l2"]["l3"]
        assert isinstance(deep, tuple)

    def test_repr_does_not_leak_attributes(self):
        ctx = TenantContext.create("t", "r", attributes={"secret": "s3cret"})
        r = repr(ctx)
        assert "s3cret" not in r
        assert "t" in r

    # --- Security remediation: strict type validation ---

    def test_tenant_id_integer_rejected(self):
        with pytest.raises(TypeError):
            TenantContext.create(123, "claim")

    def test_tenant_id_none_rejected(self):
        with pytest.raises(TypeError):
            TenantContext.create(None, "claim")

    def test_tenant_id_str_dunder_rejected(self):
        class FakeId:
            def __str__(self):
                return "fake"
        with pytest.raises(TypeError):
            TenantContext.create(FakeId(), "claim")

    def test_tenant_id_whitespace_only_rejected(self):
        with pytest.raises(ValueError):
            TenantContext.create("   ", "claim")

    def test_tenant_id_leading_space_rejected(self):
        with pytest.raises(ValueError):
            TenantContext.create(" tenant-a", "claim")

    def test_tenant_id_trailing_space_rejected(self):
        with pytest.raises(ValueError):
            TenantContext.create("tenant-a ", "claim")

    def test_resolver_id_integer_rejected(self):
        with pytest.raises(TypeError):
            TenantContext.create("t-1", 123)

    def test_resolver_id_none_rejected(self):
        with pytest.raises(TypeError):
            TenantContext.create("t-1", None)

    def test_resolver_id_whitespace_only_rejected(self):
        with pytest.raises(ValueError):
            TenantContext.create("t-1", "   ")

    def test_no_silent_trim(self):
        """Whitespace-padded tenant_id must not be silently trimmed."""
        with pytest.raises(ValueError):
            TenantContext.create(" tenant-a ", "claim")

    def test_direct_construction_also_strict(self):
        """__post_init__ must also reject non-str — not just create()."""
        with pytest.raises(TypeError):
            TenantContext(tenant_id=123, resolver_id="r")


# ---------------------------------------------------------------------------
# 2. TenantResolutionResult
# ---------------------------------------------------------------------------

class TestTenantResolutionResult:
    def test_success_properties(self):
        assert TenantResolutionResult.SUCCESS.is_success
        assert not TenantResolutionResult.SUCCESS.is_failure
        assert TenantResolutionResult.SUCCESS.short_circuits

    def test_missing_properties(self):
        assert not TenantResolutionResult.MISSING.is_success
        assert TenantResolutionResult.MISSING.is_failure
        assert not TenantResolutionResult.MISSING.short_circuits

    @pytest.mark.parametrize("result", [
        TenantResolutionResult.MALFORMED,
        TenantResolutionResult.FORBIDDEN,
        TenantResolutionResult.INTERNAL_ERROR,
    ])
    def test_failure_short_circuits(self, result):
        assert result.is_failure
        assert result.short_circuits


class TestTenantResolutionOutcome:
    def test_repr_does_not_leak_error_description(self):
        outcome = TenantResolutionOutcome.forbidden("jwt", "secret=password123")
        r = repr(outcome)
        assert "password123" not in r
        assert "forbidden" in r

    def test_repr_does_not_leak_internal_error(self):
        outcome = TenantResolutionOutcome.internal_error(
            "r", error=RuntimeError("db://user:pass@host"),
        )
        r = repr(outcome)
        assert "db://" not in r
        assert "pass" not in r


# ---------------------------------------------------------------------------
# 3. TenantResolverChain
# ---------------------------------------------------------------------------

class TestTenantResolverChain:
    def test_first_success_short_circuits(self):
        chain = TenantResolverChain()
        r1 = StubTenantResolver("r1", mode="missing")
        r2 = StubTenantResolver("r2", mode="success", tenant_id="t-1")
        chain.register(r1)
        chain.register(r2)
        outcome = _run(chain.resolve(None, Principal.create("u", "a")))
        assert outcome.is_success
        assert outcome.tenant_context.tenant_id == "t-1"

    def test_missing_falls_through(self):
        chain = TenantResolverChain()
        chain.register(StubTenantResolver("r1", mode="missing"))
        chain.register(StubTenantResolver("r2", mode="success"))
        outcome = _run(chain.resolve(None, Principal.create("u", "a")))
        assert outcome.is_success

    def test_malformed_short_circuits(self):
        chain = TenantResolverChain()
        r1 = StubTenantResolver("r1", mode="malformed")
        r2 = StubTenantResolver("r2", mode="success")
        chain.register(r1)
        chain.register(r2)
        outcome = _run(chain.resolve(None, Principal.create("u", "a")))
        assert outcome.result is TenantResolutionResult.MALFORMED
        assert r2.call_count == 0

    def test_forbidden_short_circuits(self):
        chain = TenantResolverChain()
        chain.register(StubTenantResolver("r1", mode="forbidden"))
        outcome = _run(chain.resolve(None, Principal.create("u", "a")))
        assert outcome.result is TenantResolutionResult.FORBIDDEN

    def test_all_missing_returns_missing(self):
        chain = TenantResolverChain()
        chain.register(StubTenantResolver("r1", mode="missing"))
        chain.register(StubTenantResolver("r2", mode="missing"))
        outcome = _run(chain.resolve(None, Principal.create("u", "a")))
        assert outcome.result is TenantResolutionResult.MISSING

    def test_empty_chain_returns_missing(self):
        chain = TenantResolverChain()
        outcome = _run(chain.resolve(None, Principal.create("u", "a")))
        assert outcome.result is TenantResolutionResult.MISSING

    def test_exception_wrapped_to_internal_error(self):
        chain = TenantResolverChain()
        chain.register(StubTenantResolver("boom", raise_exc=RuntimeError("db down")))
        outcome = _run(chain.resolve(None, Principal.create("u", "a")))
        assert outcome.result is TenantResolutionResult.INTERNAL_ERROR

    def test_register_requires_resolver_id(self):
        chain = TenantResolverChain()
        class NoId:
            async def resolve(self, request, principal): pass
        with pytest.raises(ValueError):
            chain.register(NoId())  # type: ignore[arg-type]

    def test_resolver_ids_preserve_order(self):
        chain = TenantResolverChain()
        chain.register(StubTenantResolver("c"))
        chain.register(StubTenantResolver("a"))
        chain.register(StubTenantResolver("b"))
        assert chain.resolver_ids == ("c", "a", "b")

    def test_is_empty(self):
        chain = TenantResolverChain()
        assert chain.is_empty
        chain.register(StubTenantResolver("x"))
        assert not chain.is_empty

    # --- Security remediation: resolver_id uniqueness and strictness ---

    def test_duplicate_resolver_id_raises_valueerror(self):
        chain = TenantResolverChain()
        chain.register(StubTenantResolver("dup"))
        with pytest.raises(ValueError, match="Duplicate resolver_id"):
            chain.register(StubTenantResolver("dup"))

    def test_non_string_resolver_id_rejected(self):
        chain = TenantResolverChain()

        class IntId:
            resolver_id = 123
            async def resolve(self, request, principal): pass
        with pytest.raises(ValueError, match="must be str"):
            chain.register(IntId())  # type: ignore[arg-type]

    def test_whitespace_only_resolver_id_rejected(self):
        chain = TenantResolverChain()

        class SpaceId:
            resolver_id = "   "
            async def resolve(self, request, principal): pass
        with pytest.raises(ValueError):
            chain.register(SpaceId())  # type: ignore[arg-type]

    def test_leading_space_resolver_id_rejected(self):
        chain = TenantResolverChain()

        class LeadingSpace:
            resolver_id = " r"
            async def resolve(self, request, principal): pass
        with pytest.raises(ValueError, match="leading or trailing whitespace"):
            chain.register(LeadingSpace())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 4. ClaimTenantResolver
# ---------------------------------------------------------------------------

class TestClaimTenantResolver:
    def _make_principal(self, claims=None):
        return Principal.create("user-1", "jwt", claims=claims or {})

    def test_success_with_valid_claim(self):
        def validator(tid, principal):
            return True

        resolver = ClaimTenantResolver(claim_name="tenant_id", validator=validator)
        principal = self._make_principal({"tenant_id": "acme-corp"})
        outcome = _run(resolver.resolve(None, principal))
        assert outcome.is_success
        assert outcome.tenant_context.tenant_id == "acme-corp"

    def test_claim_missing_returns_missing(self):
        resolver = ClaimTenantResolver(claim_name="tenant_id", validator=lambda t, p: True)
        outcome = _run(resolver.resolve(None, self._make_principal({})))
        assert outcome.result is TenantResolutionResult.MISSING

    def test_claim_not_string_returns_malformed(self):
        resolver = ClaimTenantResolver(claim_name="tenant_id", validator=lambda t, p: True)
        principal = self._make_principal({"tenant_id": 12345})
        outcome = _run(resolver.resolve(None, principal))
        assert outcome.result is TenantResolutionResult.MALFORMED

    def test_claim_none_returns_malformed(self):
        """Claim exists but value is None → MALFORMED (short-circuit, not MISSING)."""
        resolver = ClaimTenantResolver(claim_name="tenant_id", validator=lambda t, p: True)
        principal = self._make_principal({"tenant_id": None})
        outcome = _run(resolver.resolve(None, principal))
        assert outcome.result is TenantResolutionResult.MALFORMED

    def test_claim_empty_string_returns_malformed(self):
        resolver = ClaimTenantResolver(claim_name="tenant_id", validator=lambda t, p: True)
        principal = self._make_principal({"tenant_id": ""})
        outcome = _run(resolver.resolve(None, principal))
        assert outcome.result is TenantResolutionResult.MALFORMED

    def test_validator_rejection_returns_forbidden(self):
        resolver = ClaimTenantResolver(claim_name="tenant_id", validator=lambda t, p: False)
        principal = self._make_principal({"tenant_id": "bad-tenant"})
        outcome = _run(resolver.resolve(None, principal))
        assert outcome.result is TenantResolutionResult.FORBIDDEN

    def test_validator_exception_returns_internal_error(self):
        def bad_validator(tid, principal):
            raise RuntimeError("db connection lost at 10.0.0.5:5432")

        resolver = ClaimTenantResolver(claim_name="tenant_id", validator=bad_validator)
        principal = self._make_principal({"tenant_id": "acme"})
        outcome = _run(resolver.resolve(None, principal))
        assert outcome.result is TenantResolutionResult.INTERNAL_ERROR
        assert "10.0.0.5" not in repr(outcome)

    def test_empty_claim_name_rejected(self):
        with pytest.raises(ValueError):
            ClaimTenantResolver(claim_name="", validator=lambda t, p: True)

    def test_no_str_conversion_of_tenant_id(self):
        class FakeId:
            def __str__(self):
                return "fake"
        resolver = ClaimTenantResolver(claim_name="tenant_id", validator=lambda t, p: True)
        principal = self._make_principal({"tenant_id": FakeId()})
        outcome = _run(resolver.resolve(None, principal))
        assert outcome.result is TenantResolutionResult.MALFORMED

    def test_satisfies_protocol(self):
        resolver = ClaimTenantResolver(claim_name="t", validator=lambda x, y: True)
        assert isinstance(resolver, TenantResolver)

    # --- Security remediation: fail-closed validator ---

    def test_sync_validator_return_none_is_internal_error(self):
        """Non-bool return (None) → INTERNAL_ERROR, not success."""
        resolver = ClaimTenantResolver(claim_name="tid", validator=lambda t, p: None)
        principal = self._make_principal({"tid": "acme"})
        outcome = _run(resolver.resolve(None, principal))
        assert outcome.result is TenantResolutionResult.INTERNAL_ERROR

    def test_sync_validator_return_string_is_internal_error(self):
        resolver = ClaimTenantResolver(claim_name="tid", validator=lambda t, p: "yes")
        principal = self._make_principal({"tid": "acme"})
        outcome = _run(resolver.resolve(None, principal))
        assert outcome.result is TenantResolutionResult.INTERNAL_ERROR

    def test_sync_validator_return_int_is_internal_error(self):
        resolver = ClaimTenantResolver(claim_name="tid", validator=lambda t, p: 1)
        principal = self._make_principal({"tid": "acme"})
        outcome = _run(resolver.resolve(None, principal))
        assert outcome.result is TenantResolutionResult.INTERNAL_ERROR

    def test_sync_validator_return_object_is_internal_error(self):
        resolver = ClaimTenantResolver(
            claim_name="tid",
            validator=lambda t, p: object(),
        )
        principal = self._make_principal({"tid": "acme"})
        outcome = _run(resolver.resolve(None, principal))
        assert outcome.result is TenantResolutionResult.INTERNAL_ERROR

    def test_async_validator_true_succeeds(self):
        async def validator(tid, principal):
            return True
        resolver = ClaimTenantResolver(claim_name="tid", validator=validator)
        principal = self._make_principal({"tid": "acme"})
        outcome = _run(resolver.resolve(None, principal))
        assert outcome.is_success

    def test_async_validator_false_returns_forbidden(self):
        async def validator(tid, principal):
            return False
        resolver = ClaimTenantResolver(claim_name="tid", validator=validator)
        principal = self._make_principal({"tid": "acme"})
        outcome = _run(resolver.resolve(None, principal))
        assert outcome.result is TenantResolutionResult.FORBIDDEN

    def test_async_validator_none_is_internal_error(self):
        async def validator(tid, principal):
            return None
        resolver = ClaimTenantResolver(claim_name="tid", validator=validator)
        principal = self._make_principal({"tid": "acme"})
        outcome = _run(resolver.resolve(None, principal))
        assert outcome.result is TenantResolutionResult.INTERNAL_ERROR

    def test_async_validator_exception_is_internal_error(self):
        async def validator(tid, principal):
            raise RuntimeError("connection refused at 10.0.0.5")
        resolver = ClaimTenantResolver(claim_name="tid", validator=validator)
        principal = self._make_principal({"tid": "acme"})
        outcome = _run(resolver.resolve(None, principal))
        assert outcome.result is TenantResolutionResult.INTERNAL_ERROR
        assert "10.0.0.5" not in repr(outcome)

    def test_async_validator_cancelled_propagates(self):
        """asyncio.CancelledError must propagate, never be swallowed."""
        async def validator(tid, principal):
            raise asyncio.CancelledError()

        resolver = ClaimTenantResolver(claim_name="tid", validator=validator)
        principal = self._make_principal({"tid": "acme"})
        with pytest.raises(asyncio.CancelledError):
            _run(resolver.resolve(None, principal))

    def test_attributes_claim_removed(self):
        """ClaimTenantResolver no longer accepts attributes_claim parameter."""
        with pytest.raises(TypeError):
            ClaimTenantResolver(
                claim_name="tid",
                validator=lambda t, p: True,
                attributes_claim="attrs",
            )

    def test_resolver_id_no_str_conversion(self):
        with pytest.raises((TypeError, ValueError)):
            ClaimTenantResolver(
                claim_name="tid",
                validator=lambda t, p: True,
                resolver_id=123,  # type: ignore[arg-type]
            )

    # --- Constructor-time validation (Item 5) ---

    def test_constructor_validator_not_callable_raises_typeerror(self):
        with pytest.raises(TypeError, match="callable"):
            ClaimTenantResolver(claim_name="tid", validator=42)  # type: ignore[arg-type]

    def test_constructor_validator_none_raises(self):
        with pytest.raises((TypeError, ValueError)):
            ClaimTenantResolver(claim_name="tid", validator=None)  # type: ignore[arg-type]

    def test_constructor_claim_name_whitespace_only_rejected(self):
        with pytest.raises(ValueError, match="claim_name"):
            ClaimTenantResolver(
                claim_name="   ",
                validator=lambda t, p: True,
            )

    def test_constructor_claim_name_leading_space_rejected(self):
        with pytest.raises(ValueError, match="claim_name"):
            ClaimTenantResolver(
                claim_name=" tid",
                validator=lambda t, p: True,
            )

    def test_constructor_claim_name_trailing_space_rejected(self):
        with pytest.raises(ValueError, match="claim_name"):
            ClaimTenantResolver(
                claim_name="tid ",
                validator=lambda t, p: True,
            )

    def test_constructor_claim_name_non_string_rejected(self):
        with pytest.raises(ValueError):
            ClaimTenantResolver(claim_name=123, validator=lambda t, p: True)  # type: ignore[arg-type]

    # --- Exception propagation (Item 4) ---

    def test_system_exit_propagates(self):
        """SystemExit must propagate, never be swallowed as INTERNAL_ERROR."""
        def validator(tid, principal):
            raise SystemExit(1)
        resolver = ClaimTenantResolver(claim_name="tid", validator=validator)
        principal = self._make_principal({"tid": "acme"})
        with pytest.raises(SystemExit):
            _run(resolver.resolve(None, principal))

    def test_generator_exit_propagates(self):
        """GeneratorExit must propagate, never be swallowed."""
        def validator(tid, principal):
            raise GeneratorExit()
        resolver = ClaimTenantResolver(claim_name="tid", validator=validator)
        principal = self._make_principal({"tid": "acme"})
        with pytest.raises(GeneratorExit):
            _run(resolver.resolve(None, principal))

    def test_sync_cancelled_error_propagates(self):
        """asyncio.CancelledError (sync raise) must propagate."""
        def validator(tid, principal):
            raise asyncio.CancelledError()
        resolver = ClaimTenantResolver(claim_name="tid", validator=validator)
        principal = self._make_principal({"tid": "acme"})
        with pytest.raises(asyncio.CancelledError):
            _run(resolver.resolve(None, principal))

    # --- Whitespace claim strictness (Item 3) ---

    def test_whitespace_only_claim_returns_malformed(self):
        resolver = ClaimTenantResolver(claim_name="tid", validator=lambda t, p: True)
        principal = self._make_principal({"tid": "   "})
        outcome = _run(resolver.resolve(None, principal))
        assert outcome.result is TenantResolutionResult.MALFORMED

    def test_leading_space_claim_returns_malformed(self):
        resolver = ClaimTenantResolver(claim_name="tid", validator=lambda t, p: True)
        principal = self._make_principal({"tid": " acme"})
        outcome = _run(resolver.resolve(None, principal))
        assert outcome.result is TenantResolutionResult.MALFORMED

    def test_trailing_space_claim_returns_malformed(self):
        resolver = ClaimTenantResolver(claim_name="tid", validator=lambda t, p: True)
        principal = self._make_principal({"tid": "acme "})
        outcome = _run(resolver.resolve(None, principal))
        assert outcome.result is TenantResolutionResult.MALFORMED

    def test_malformed_whitespace_skips_validator(self):
        """When claim has whitespace issues, validator must not be called."""
        call_count = {"n": 0}

        def counting_validator(tid, principal):
            call_count["n"] += 1
            return True

        resolver = ClaimTenantResolver(claim_name="tid", validator=counting_validator)
        for bad in ("", "   ", " acme", "acme "):
            principal = self._make_principal({"tid": bad})
            outcome = _run(resolver.resolve(None, principal))
            assert outcome.result is TenantResolutionResult.MALFORMED, f"Failed for {bad!r}"
        assert call_count["n"] == 0


# ---------------------------------------------------------------------------
# 5. StubTenantResolver
# ---------------------------------------------------------------------------

class TestStubTenantResolver:
    @pytest.mark.parametrize("mode_str,result", [
        ("success", TenantResolutionResult.SUCCESS),
        ("missing", TenantResolutionResult.MISSING),
        ("malformed", TenantResolutionResult.MALFORMED),
        ("forbidden", TenantResolutionResult.FORBIDDEN),
        ("internal_error", TenantResolutionResult.INTERNAL_ERROR),
    ])
    def test_all_modes(self, mode_str, result):
        stub = StubTenantResolver("test", mode=mode_str)
        outcome = _run(stub.resolve(None, Principal.create("u", "a")))
        assert outcome.result is result

    def test_callable_mode(self):
        def custom(request, principal):
            return TenantResolutionOutcome.forbidden("custom", "banned")
        stub = StubTenantResolver("test", mode=custom)
        outcome = _run(stub.resolve(None, Principal.create("u", "a")))
        assert outcome.result is TenantResolutionResult.FORBIDDEN

    def test_call_count(self):
        stub = StubTenantResolver("test", mode="success")
        _run(stub.resolve(None, Principal.create("u", "a")))
        _run(stub.resolve(None, Principal.create("u", "a")))
        assert stub.call_count == 2

    def test_satisfies_protocol(self):
        assert isinstance(StubTenantResolver("test"), TenantResolver)


# ---------------------------------------------------------------------------
# 6. RoutePolicy tenant_required compilation
# ---------------------------------------------------------------------------

class TestRoutePolicyTenantRequired:
    def test_tenant_required_defaults_false(self):
        from lingshu.system.policy import RoutePolicyRegistry
        compiled = RoutePolicyDefinition().compile("test_route")
        assert compiled.tenant_required is False

    def test_tenant_required_true_compiles(self):
        compiled = RoutePolicyDefinition(tenant_required=True).compile("test_route")
        assert compiled.tenant_required is True

    def test_public_and_tenant_required_rejected(self):
        with pytest.raises(Exception, match="tenant"):
            RoutePolicyDefinition(public=True, tenant_required=True)

    def test_auth_required_false_and_tenant_required_rejected(self):
        with pytest.raises(Exception, match="tenant"):
            RoutePolicyDefinition(auth_required=False, tenant_required=True)

    def test_compile_rejects_public_tenant(self):
        with pytest.raises(Exception, match="tenant"):
            RoutePolicyDefinition(public=True, tenant_required=True).compile("x")

    def test_compile_rejects_unauth_tenant(self):
        with pytest.raises(Exception, match="tenant"):
            RoutePolicyDefinition(auth_required=False, tenant_required=True)


# ---------------------------------------------------------------------------
# 7. Middleware fail-closed (403)
# ---------------------------------------------------------------------------

class TestFailClosedTenantMiddleware:
    def _make_app(self, name, tenant_chain=None, auth_subject="test-user"):
        auth_chain = AuthenticatorChain()
        auth_chain.register(StubAuthenticator("jwt", mode="success", subject=auth_subject))
        return _make_authed_tenant_app(name, auth_chain=auth_chain, tenant_chain=tenant_chain)

    def test_no_chain_registered_returns_403(self):
        app = self._make_app("tenant-no-chain", tenant_chain=None)
        _, response = asyncio.run(app.asgi_client.get("/tenant-no-chain/tenant"))
        assert response.status == 403
        assert response.json["code"] == 990124

    def test_empty_chain_returns_403(self):
        chain = TenantResolverChain()
        app = self._make_app("tenant-empty-chain", tenant_chain=chain)
        _, response = asyncio.run(app.asgi_client.get("/tenant-empty-chain/tenant"))
        assert response.status == 403
        assert response.json["code"] == 990124

    def test_missing_returns_403(self):
        chain = TenantResolverChain()
        chain.register(StubTenantResolver("r", mode="missing"))
        app = self._make_app("tenant-missing", tenant_chain=chain)
        _, response = asyncio.run(app.asgi_client.get("/tenant-missing/tenant"))
        assert response.status == 403
        assert response.json["code"] == 990120

    def test_malformed_returns_403(self):
        chain = TenantResolverChain()
        chain.register(StubTenantResolver("r", mode="malformed"))
        app = self._make_app("tenant-malformed", tenant_chain=chain)
        _, response = asyncio.run(app.asgi_client.get("/tenant-malformed/tenant"))
        assert response.status == 403
        assert response.json["code"] == 990121

    def test_forbidden_returns_403(self):
        chain = TenantResolverChain()
        chain.register(StubTenantResolver("r", mode="forbidden"))
        app = self._make_app("tenant-forbidden", tenant_chain=chain)
        _, response = asyncio.run(app.asgi_client.get("/tenant-forbidden/tenant"))
        assert response.status == 403
        assert response.json["code"] == 990122

    def test_internal_error_returns_403(self):
        chain = TenantResolverChain()
        chain.register(StubTenantResolver("r", mode="internal_error"))
        app = self._make_app("tenant-internal", tenant_chain=chain)
        _, response = asyncio.run(app.asgi_client.get("/tenant-internal/tenant"))
        assert response.status == 403
        assert response.json["code"] == 990123

    def test_success_binds_tenant(self):
        chain = TenantResolverChain()
        chain.register(StubTenantResolver("r", mode="success", tenant_id="acme"))
        app = self._make_app("tenant-success", tenant_chain=chain)
        _, response = asyncio.run(app.asgi_client.get("/tenant-success/tenant"))
        assert response.status == 200
        assert response.json["data"]["tenant_id"] == "acme"

    def test_non_tenant_route_works_without_chain(self):
        """Protected route without tenant_required should work fine."""
        app = self._make_app("tenant-not-required")
        _, response = asyncio.run(app.asgi_client.get("/tenant-not-required/protected"))
        assert response.status == 200

    def test_403_does_not_leak_error_description(self):
        def evil_mode(request, principal):
            return TenantResolutionOutcome.forbidden("evil", "secret=db_password:Hunter2")

        chain = TenantResolverChain()
        chain.register(StubTenantResolver("evil", mode=evil_mode))
        app = self._make_app("tenant-leak", tenant_chain=chain)
        _, response = asyncio.run(app.asgi_client.get("/tenant-leak/tenant"))
        assert response.status == 403
        body = str(response.json)
        assert "Hunter2" not in body
        assert "db_password" not in body


# ---------------------------------------------------------------------------
# 8. request.tenant semantics
# ---------------------------------------------------------------------------

class TestRequestTenantSemantics:
    def test_no_context_raises(self):
        from lingshu.system.proxies import RequestProxy
        proxy = RequestProxy()
        with pytest.raises(NoRequestContextError):
            _ = proxy.tenant

    def test_non_tenant_route_returns_none(self):
        auth_chain = AuthenticatorChain()
        auth_chain.register(StubAuthenticator("jwt", mode="success", subject="u"))
        app = _make_authed_tenant_app("tenant-proxy-none", auth_chain=auth_chain)
        _, response = asyncio.run(app.asgi_client.get("/tenant-proxy-none/protected"))
        assert response.status == 200

    def test_tenant_route_returns_context(self):
        auth_chain = AuthenticatorChain()
        auth_chain.register(StubAuthenticator("jwt", mode="success", subject="u"))
        tenant_chain = TenantResolverChain()
        tenant_chain.register(StubTenantResolver("r", mode="success", tenant_id="t-1"))
        app = _make_authed_tenant_app("tenant-proxy-set", auth_chain=auth_chain, tenant_chain=tenant_chain)
        _, response = asyncio.run(app.asgi_client.get("/tenant-proxy-set/tenant"))
        assert response.status == 200
        assert response.json["data"]["tenant_id"] == "t-1"


# ---------------------------------------------------------------------------
# 9. Cleanup lifecycle
# ---------------------------------------------------------------------------

class TestTenantCleanupLifecycle:
    def test_cleanup_after_normal_return(self):
        auth_chain = AuthenticatorChain()
        auth_chain.register(StubAuthenticator("jwt", mode="success", subject="u"))
        tenant_chain = TenantResolverChain()
        tenant_chain.register(StubTenantResolver("r", mode="success", tenant_id="t-clean"))
        app = _make_authed_tenant_app("tenant-clean-normal", auth_chain, tenant_chain)
        _, response = asyncio.run(app.asgi_client.get("/tenant-clean-normal/tenant"))
        assert response.status == 200
        assert current_tenant.get() is None

    def test_cleanup_after_handler_exception(self):
        from lingshu.system import sanic_adapter
        from lingshu.system.auth.middleware import install_authentication_middleware, set_authenticator_chain
        from lingshu.system.auth.tenant.middleware import install_tenant_middleware, set_tenant_resolver_chain

        app = Sanic("tenant-clean-exc")
        sanic_adapter.install_context_middleware(app)
        bp = Blueprint("tenant-clean-exc-bp", url_prefix="/tce")

        @bp.get("/boom", name="boom")
        async def boom_handler(request):
            raise RuntimeError("boom")

        set_route_policy(boom_handler, RoutePolicyDefinition(tenant_required=True))
        app.blueprint(bp)
        compile_route_policies(app)

        auth_chain = AuthenticatorChain()
        auth_chain.register(StubAuthenticator("jwt", mode="success", subject="u"))
        set_authenticator_chain(app, auth_chain)

        tenant_chain = TenantResolverChain()
        tenant_chain.register(StubTenantResolver("r", mode="success", tenant_id="t"))
        set_tenant_resolver_chain(app, tenant_chain)

        install_authentication_middleware(app)
        install_tenant_middleware(app)

        _, response = asyncio.run(app.asgi_client.get("/tce/boom"))
        assert response.status == 500
        assert current_tenant.get() is None

    def test_cleanup_after_cancellation(self):
        from lingshu.system import sanic_adapter
        from lingshu.system.auth.middleware import install_authentication_middleware, set_authenticator_chain
        from lingshu.system.auth.tenant.middleware import install_tenant_middleware, set_tenant_resolver_chain

        app = Sanic("tenant-clean-cancel")
        sanic_adapter.install_context_middleware(app)
        bp = Blueprint("tenant-clean-cancel-bp", url_prefix="/tcc")

        handler_entered = asyncio.Event()
        captured = {}
        cancel_mode = {"cancelled": False}

        @bp.get("/cancel", name="cancel")
        async def cancel_handler(request):
            from lingshu.response import json_response
            captured["binding"] = request.ctx.lingshu_tenant_binding
            captured["request"] = request
            handler_entered.set()
            if cancel_mode["cancelled"]:
                return json_response({"ok": True})
            await asyncio.sleep(30)
            return None

        set_route_policy(cancel_handler, RoutePolicyDefinition(tenant_required=True, timeout=60.0))
        app.blueprint(bp)
        compile_route_policies(app)

        auth_chain = AuthenticatorChain()
        auth_chain.register(StubAuthenticator("jwt", mode="success", subject="u"))
        set_authenticator_chain(app, auth_chain)

        tenant_chain = TenantResolverChain()
        tenant_chain.register(StubTenantResolver("r", mode="success", tenant_id="t-cancel"))
        set_tenant_resolver_chain(app, tenant_chain)

        install_authentication_middleware(app)
        install_tenant_middleware(app)

        async def scenario():
            cleanup_done = asyncio.Event()
            request_task = asyncio.ensure_future(app.asgi_client.get("/tcc/cancel"))
            request_task.add_done_callback(lambda _t: cleanup_done.set())
            await handler_entered.wait()

            binding = captured["binding"]
            assert binding is not None
            assert binding.tenant_context.tenant_id == "t-cancel"

            request_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await request_task

            await asyncio.wait_for(cleanup_done.wait(), timeout=5.0)

            assert captured["request"].ctx.lingshu_tenant_binding is None
            assert captured["binding"].reset_done is True

            cancel_mode["cancelled"] = True
            _, resp = await app.asgi_client.get("/tcc/cancel")
            assert resp.status == 200

        asyncio.run(scenario())


# ---------------------------------------------------------------------------
# 10. Concurrent isolation (100+)
# ---------------------------------------------------------------------------

class TestConcurrentTenantIsolation:
    def test_100_concurrent_no_tenant_leak(self):
        def mode_fn(request, principal):
            tenant = request.headers.get("X-Tenant", None)
            if tenant is None:
                return TenantResolutionOutcome.missing("stub")
            return TenantResolutionOutcome.success(
                TenantContext.create(tenant, "stub")
            )

        auth_chain = AuthenticatorChain()
        auth_chain.register(StubAuthenticator("jwt", mode="success", subject="u"))
        tenant_chain = TenantResolverChain()
        tenant_chain.register(StubTenantResolver("stub", mode=mode_fn))
        app = _make_authed_tenant_app("conc-tenant", auth_chain, tenant_chain)

        async def fetch(tenant_id):
            _, resp = await app.asgi_client.get(
                "/conc-tenant/tenant",
                headers={"X-Tenant": tenant_id},
            )
            return tenant_id, resp.status, resp.json["data"]["tenant_id"]

        async def run_all():
            tenants = [f"tenant-{i}" for i in range(100)]
            return await asyncio.gather(*[fetch(t) for t in tenants])

        results = asyncio.run(run_all())
        for tenant_id, status, resolved in results:
            assert status == 200, f"{tenant_id} got {status}"
            assert resolved == tenant_id


# ---------------------------------------------------------------------------
# 11. Multi-app isolation
# ---------------------------------------------------------------------------

class TestMultiAppTenantIsolation:
    def test_separate_apps_have_independent_chains(self):
        auth_a = AuthenticatorChain()
        auth_a.register(StubAuthenticator("jwt", mode="success", subject="u"))
        tenant_a = TenantResolverChain()
        tenant_a.register(StubTenantResolver("ra", mode="success", tenant_id="ta"))

        auth_b = AuthenticatorChain()
        auth_b.register(StubAuthenticator("jwt", mode="success", subject="u"))
        tenant_b = TenantResolverChain()
        tenant_b.register(StubTenantResolver("rb", mode="missing"))

        app_a = _make_authed_tenant_app("iso-a", auth_a, tenant_a)
        app_b = _make_authed_tenant_app("iso-b", auth_b, tenant_b)

        _, resp_a = asyncio.run(app_a.asgi_client.get("/iso-a/tenant"))
        assert resp_a.status == 200
        assert resp_a.json["data"]["tenant_id"] == "ta"

        _, resp_b = asyncio.run(app_b.asgi_client.get("/iso-b/tenant"))
        assert resp_b.status == 403


# ---------------------------------------------------------------------------
# 12. Idempotent middleware / configure
# ---------------------------------------------------------------------------

class TestIdempotentTenantMiddleware:
    def test_double_install_single_resolution_per_request(self):
        from lingshu.system import sanic_adapter
        from lingshu.system.auth.middleware import install_authentication_middleware, set_authenticator_chain
        from lingshu.system.auth.tenant.middleware import install_tenant_middleware, set_tenant_resolver_chain

        app = Sanic("tenant-idempotent")
        sanic_adapter.install_context_middleware(app)
        bp = Blueprint("tenant-idempotent-bp", url_prefix="/ti")

        @bp.get("/tenant", name="tenant")
        async def t_handler(request):
            from lingshu.response import json_response
            return json_response({"tenant_id": current_tenant.get().tenant_id if current_tenant.get() else None})

        set_route_policy(t_handler, RoutePolicyDefinition(tenant_required=True))
        app.blueprint(bp)
        compile_route_policies(app)

        auth_chain = AuthenticatorChain()
        auth_chain.register(StubAuthenticator("jwt", mode="success", subject="u"))
        set_authenticator_chain(app, auth_chain)

        stub = StubTenantResolver("r", mode="success", tenant_id="t-1")
        chain = TenantResolverChain()
        chain.register(stub)
        set_tenant_resolver_chain(app, chain)

        install_authentication_middleware(app)
        install_tenant_middleware(app)
        install_tenant_middleware(app)  # idempotent

        _, response = asyncio.run(app.asgi_client.get("/ti/tenant"))
        assert response.status == 200
        assert response.json["data"]["tenant_id"] == "t-1"
        assert stub.call_count == 1


# ---------------------------------------------------------------------------
# 13. Import order stability
# ---------------------------------------------------------------------------

class TestImportOrderStability:
    def test_import_lingshu_then_tenant(self):
        import lingshu
        import lingshu.tenant
        assert lingshu.tenant.TenantContext is not None
        assert lingshu.tenant.TenantResolverChain is not None

    def test_import_tenant_then_lingshu(self):
        import lingshu.tenant
        import lingshu
        assert lingshu.tenant.TenantContext is not None

    def test_from_lingshu_import_tenant(self):
        import lingshu.tenant
        from lingshu import tenant
        assert tenant is lingshu.tenant
        assert tenant.TenantContext is not None


# ---------------------------------------------------------------------------
# 14. create_app integration
# ---------------------------------------------------------------------------

class TestCreateAppTenantIntegration:
    def test_tenant_required_403_without_chain(self):
        from lingshu.app import create_app

        app = create_app()
        bp = Blueprint("tenant-integ", url_prefix="/tinteg")

        @bp.get("/tenant", name="tenant")
        async def t_handler(request):
            from lingshu.response import json_response
            return json_response({"ok": True})

        set_route_policy(t_handler, RoutePolicyDefinition(tenant_required=True))
        app.blueprint(bp)
        compile_route_policies(app)

        _, response = asyncio.run(app.asgi_client.get("/tinteg/tenant"))
        assert response.status == 401  # auth fails first (no auth chain)

    def test_public_route_works_without_chain(self):
        from lingshu.app import create_app

        app = create_app()
        bp = Blueprint("tenant-public-integ", url_prefix="/tpi")

        @bp.get("/open", name="open")
        async def open_h(request):
            from lingshu.response import json_response
            return json_response({"ok": True})

        set_route_policy(open_h, RoutePolicyDefinition(public=True))
        app.blueprint(bp)
        compile_route_policies(app)

        _, response = asyncio.run(app.asgi_client.get("/tpi/open"))
        assert response.status == 200


# ---------------------------------------------------------------------------
# 15. Security remediation: lifecycle, public API, 403 contract
# ---------------------------------------------------------------------------

class TestTimeoutCleanup:
    """Timeout path must clean up tenant binding — deterministic wait."""

    def test_tenant_binding_cleanup_on_timeout(self):
        from lingshu.system import sanic_adapter
        from lingshu.system.auth.middleware import (
            install_authentication_middleware,
            set_authenticator_chain,
        )
        from lingshu.system.auth.tenant.middleware import (
            install_tenant_middleware,
            set_tenant_resolver_chain,
        )

        app = Sanic("tenant-timeout-deterministic")
        sanic_adapter.install_context_middleware(app)
        bp = Blueprint("tenant-timeout-det-bp", url_prefix="/ttd")

        handler_started = asyncio.Event()
        captured = {}

        @bp.get("/slow", name="slow")
        async def slow_handler(request):
            captured["binding"] = request.ctx.lingshu_tenant_binding
            handler_started.set()
            await asyncio.sleep(30)
            from lingshu.response import json_response
            return json_response({"ok": True})

        set_route_policy(slow_handler, RoutePolicyDefinition(tenant_required=True, timeout=0.05))
        app.blueprint(bp)
        compile_route_policies(app)

        auth_chain = AuthenticatorChain()
        auth_chain.register(StubAuthenticator("jwt", mode="success", subject="u"))
        set_authenticator_chain(app, auth_chain)

        tenant_chain = TenantResolverChain()
        tenant_chain.register(StubTenantResolver("r", mode="success", tenant_id="t-to"))
        set_tenant_resolver_chain(app, tenant_chain)

        install_authentication_middleware(app)
        install_tenant_middleware(app)

        async def scenario():
            task = asyncio.ensure_future(app.asgi_client.get("/ttd/slow"))
            await handler_started.wait()

            binding = captured["binding"]
            assert binding is not None
            assert binding.tenant_context.tenant_id == "t-to"

            # Deterministically await the full request task to completion.
            _, response = await task

            # HTTP 504 with error code 990002.
            assert response.status == 504
            assert response.json["code"] == 990002

            # Tenant binding was cleaned up.
            assert binding.reset_done is True
            assert current_tenant.get() is None

            # Follow-up request must NOT see the previous tenant context.
            _, resp2 = await app.asgi_client.get("/ttd/slow")
            assert resp2.status == 504
            assert current_tenant.get() is None

        asyncio.run(scenario())


class TestRealCreateAppIntegration:
    """Tests using the real create_app() entry point."""

    def test_non_tenant_route_tenant_is_none(self):
        """A non-tenant-required route must have request.tenant is None."""
        from lingshu.app import create_app

        app = create_app()
        bp = Blueprint("rca-nt", url_prefix="/rca")

        @bp.get("/check", name="check")
        async def check_handler(request):
            from lingshu.response import json_response
            from lingshu.system.proxies import RequestProxy
            proxy = RequestProxy()
            return json_response({"tenant": proxy.tenant})

        set_route_policy(check_handler, RoutePolicyDefinition(public=True))
        app.blueprint(bp)
        compile_route_policies(app)

        _, response = asyncio.run(app.asgi_client.get("/rca/check"))
        assert response.status == 200
        assert response.json["data"]["tenant"] is None

    def test_create_app_tenant_middleware_installed(self):
        """create_app() must install tenant middleware unconditionally."""
        from lingshu.app import create_app

        app = create_app()
        assert getattr(app.ctx, "lingshu_tenant_middleware_installed", False) is True


class TestPublicAPISmoke:
    """Public API smoke tests."""

    def test_tenant_public_api_is_accessible(self):
        """Business code can use lingshu.tenant without importing lingshu.system."""
        import lingshu.tenant

        # All public exports must be non-None
        for name in lingshu.tenant.__all__:
            obj = getattr(lingshu.tenant, name, None)
            assert obj is not None, f"{name} is missing from lingshu.tenant"

    def test_tenant_public_api_exports(self):
        import lingshu.tenant

        assert hasattr(lingshu.tenant, "TenantContext")
        assert hasattr(lingshu.tenant, "TenantResolverChain")
        assert hasattr(lingshu.tenant, "ClaimTenantResolver")
        assert hasattr(lingshu.tenant, "TenantResolver")


class Test403Contract:
    """403 response must preserve request_id/trace_id and leak nothing."""

    def _make_app(self, name):
        auth_chain = AuthenticatorChain()
        auth_chain.register(StubAuthenticator("jwt", mode="success", subject="u"))
        return _make_authed_tenant_app(name, auth_chain=auth_chain, tenant_chain=None)

    def test_403_preserves_request_id(self):
        app = self._make_app("tenant-rid")
        custom_rid = "test-request-id-abc123"
        _, response = asyncio.run(
            app.asgi_client.get(
                "/tenant-rid/tenant",
                headers={"X-Request-ID": custom_rid},
            )
        )
        assert response.status == 403
        assert response.json["data"]["request_id"] == custom_rid

    def test_403_preserves_trace_id(self):
        app = self._make_app("tenant-tid")
        custom_trace = "test-trace-id-xyz789"
        _, response = asyncio.run(
            app.asgi_client.get(
                "/tenant-tid/tenant",
                headers={"X-Trace-ID": custom_trace},
            )
        )
        assert response.status == 403
        assert response.json["data"]["trace_id"] == custom_trace

    def test_403_no_claim_leakage(self):
        """403 must not leak the raw claim value."""
        from lingshu.system.auth.tenant.middleware import (
            install_tenant_middleware,
            set_tenant_resolver_chain,
        )
        from lingshu.system import sanic_adapter
        from lingshu.system.auth.middleware import (
            install_authentication_middleware,
            set_authenticator_chain,
        )

        app = Sanic("tenant-leak-claim")
        sanic_adapter.install_context_middleware(app)
        bp = Blueprint("tlc-bp", url_prefix="/tlc")

        @bp.get("/tenant", name="tenant")
        async def t_handler(request):
            from lingshu.response import json_response
            return json_response({"ok": True})

        set_route_policy(t_handler, RoutePolicyDefinition(tenant_required=True))
        app.blueprint(bp)
        compile_route_policies(app)

        auth_chain = AuthenticatorChain()
        auth_chain.register(StubAuthenticator("jwt", mode="success", subject="u"))
        set_authenticator_chain(app, auth_chain)

        def evil_mode(request, principal):
            return TenantResolutionOutcome.forbidden(
                "evil",
                "claim=super-secret-jwt-value-12345",
            )

        chain = TenantResolverChain()
        chain.register(StubTenantResolver("evil", mode=evil_mode))
        set_tenant_resolver_chain(app, chain)
        install_authentication_middleware(app)
        install_tenant_middleware(app)

        _, response = asyncio.run(app.asgi_client.get("/tlc/tenant"))
        assert response.status == 403
        body = str(response.json)
        assert "super-secret-jwt-value-12345" not in body
        assert "claim=" not in body

    def test_403_no_exception_leakage(self):
        """403 must not leak validator exception messages."""
        from lingshu.system.auth.tenant.middleware import (
            install_tenant_middleware,
            set_tenant_resolver_chain,
        )
        from lingshu.system import sanic_adapter
        from lingshu.system.auth.middleware import (
            install_authentication_middleware,
            set_authenticator_chain,
        )

        app = Sanic("tenant-leak-exc")
        sanic_adapter.install_context_middleware(app)
        bp = Blueprint("tle-bp", url_prefix="/tle")

        @bp.get("/tenant", name="tenant")
        async def t_handler(request):
            from lingshu.response import json_response
            return json_response({"ok": True})

        set_route_policy(t_handler, RoutePolicyDefinition(tenant_required=True))
        app.blueprint(bp)
        compile_route_policies(app)

        auth_chain = AuthenticatorChain()
        auth_chain.register(StubAuthenticator("jwt", mode="success", subject="u"))
        set_authenticator_chain(app, auth_chain)

        chain = TenantResolverChain()
        chain.register(
            StubTenantResolver("boom", raise_exc=RuntimeError("db://user:pass@host:5432"))
        )
        set_tenant_resolver_chain(app, chain)
        install_authentication_middleware(app)
        install_tenant_middleware(app)

        _, response = asyncio.run(app.asgi_client.get("/tle/tenant"))
        assert response.status == 403
        body = str(response.json)
        assert "db://" not in body
        assert "pass" not in body
        assert "5432" not in body

    def test_403_no_password_in_msg(self):
        """403 response message must not contain password-like strings."""
        app = self._make_app("tenant-pw")
        _, response = asyncio.run(app.asgi_client.get("/tenant-pw/tenant"))
        assert response.status == 403
        msg = response.json.get("msg", "")
        assert "password" not in msg.lower()
        assert "secret" not in msg.lower()


# ---------------------------------------------------------------------------
# 16. Real create_app + public API end-to-end
# ---------------------------------------------------------------------------

class TestPublicAPIEndToEnd:
    """End-to-end tests using ONLY the public API surface.

    Handler code uses ``from lingshu import request`` — never imports
    ``lingshu.system.*`` directly.
    """

    def test_scenario1_authed_no_tenant_chain_returns_990124(self):
        """Scenario 1: auth configured, tenant_required=True, no chain → 990124."""
        from lingshu.app import create_app
        from lingshu.auth import (
            AuthenticatorChain,
            JwtBearerAuthenticator,
            configure_authentication,
        )

        app = create_app()
        bp = Blueprint("e2e-s1", url_prefix="/e2e1")

        @bp.get("/tenant", name="tenant")
        async def tenant_handler(request):
            from lingshu import request
            from lingshu.response import json_response
            return json_response({"tenant_id": request.tenant.tenant_id if request.tenant else None})

        set_route_policy(tenant_handler, RoutePolicyDefinition(tenant_required=True))
        app.blueprint(bp)
        compile_route_policies(app)

        chain = AuthenticatorChain()
        chain.register(
            JwtBearerAuthenticator(secret=_TEST_SECRET, algorithms=["HS256"])
        )
        configure_authentication(app, chain)

        from lingshu.system.auth.jwt_test_helpers import encode_jwt_token
        token = encode_jwt_token(_TEST_SECRET, "HS256", subject="user-1")
        _, response = asyncio.run(
            app.asgi_client.get(
                "/e2e1/tenant",
                headers={"Authorization": f"Bearer {token}"},
            )
        )
        assert response.status == 403
        assert response.json["code"] == 990124

    def test_scenario2_authed_with_claim_resolver_success(self):
        """Scenario 2: full end-to-end via public API.

        Handler uses ONLY:
            from lingshu import request
            request.principal
            request.tenant
        """
        from lingshu.app import create_app
        from lingshu.auth import (
            AuthenticatorChain,
            JwtBearerAuthenticator,
            configure_authentication,
        )
        from lingshu.tenant import (
            ClaimTenantResolver,
            TenantResolverChain,
            configure_tenant_resolution,
        )

        app = create_app()
        bp = Blueprint("e2e-s2", url_prefix="/e2e2")

        @bp.get("/me", name="me")
        async def me_handler(request):
            from lingshu import request
            from lingshu.response import json_response
            return json_response({
                "subject": request.principal.subject,
                "tenant_id": request.tenant.tenant_id if request.tenant else None,
            })

        set_route_policy(me_handler, RoutePolicyDefinition(tenant_required=True))
        app.blueprint(bp)
        compile_route_policies(app)

        auth_chain = AuthenticatorChain()
        auth_chain.register(
            JwtBearerAuthenticator(secret=_TEST_SECRET, algorithms=["HS256"])
        )
        configure_authentication(app, auth_chain)

        valid_tenants = {"acme-corp", "globex"}

        tenant_chain = TenantResolverChain()
        tenant_chain.register(
            ClaimTenantResolver(
                claim_name="tenant_id",
                validator=lambda tid, p: tid in valid_tenants,
            )
        )
        configure_tenant_resolution(app, tenant_chain)

        from lingshu.system.auth.jwt_test_helpers import encode_jwt_token
        token = encode_jwt_token(
            _TEST_SECRET, "HS256",
            subject="user-1",
            extra_claims={"tenant_id": "acme-corp"},
        )
        _, response = asyncio.run(
            app.asgi_client.get(
                "/e2e2/me",
                headers={"Authorization": f"Bearer {token}"},
            )
        )
        assert response.status == 200
        assert response.json["data"]["subject"] == "user-1"
        assert response.json["data"]["tenant_id"] == "acme-corp"

    def test_scenario3_non_tenant_route_tenant_is_none(self):
        """Scenario 3: non-tenant_required route — request.tenant is None."""
        from lingshu.app import create_app
        from lingshu.auth import (
            AuthenticatorChain,
            JwtBearerAuthenticator,
            configure_authentication,
        )

        app = create_app()
        bp = Blueprint("e2e-s3", url_prefix="/e2e3")

        @bp.get("/me", name="me")
        async def me_handler(request):
            from lingshu import request
            from lingshu.response import json_response
            return json_response({
                "subject": request.principal.subject,
                "tenant": request.tenant,
            })

        set_route_policy(me_handler, RoutePolicyDefinition())
        app.blueprint(bp)
        compile_route_policies(app)

        auth_chain = AuthenticatorChain()
        auth_chain.register(
            JwtBearerAuthenticator(secret=_TEST_SECRET, algorithms=["HS256"])
        )
        configure_authentication(app, auth_chain)

        from lingshu.system.auth.jwt_test_helpers import encode_jwt_token
        token = encode_jwt_token(_TEST_SECRET, "HS256", subject="user-1")
        _, response = asyncio.run(
            app.asgi_client.get(
                "/e2e3/me",
                headers={"Authorization": f"Bearer {token}"},
            )
        )
        assert response.status == 200
        assert response.json["data"]["subject"] == "user-1"
        assert response.json["data"]["tenant"] is None
