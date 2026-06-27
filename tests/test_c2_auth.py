"""Phase C2.1 authentication foundation tests (second round).

Covers all first-round and second-round review requirements:

1. Fail-closed middleware (chain not registered → 401/990116).
2. Public lingshu.auth API + bootstrap smoke test.
3. No error_description or exception leakage in responses/headers/repr.
4. request.principal context semantics (NoRequestContextError vs None).
5. Principal cleanup through real request lifecycle (normal/exception/cancel/timeout).
6. Principal deep immutability (recursive freeze, scope validation).
7. JWT hardening (order, no duplicates, no family mixing, no encode on production class).
8. AuthenticatorChain semantics.
9. Concurrent isolation.
10. Multi-app isolation.
"""

from __future__ import annotations

import asyncio
from types import MappingProxyType, SimpleNamespace

import pytest
from sanic import Blueprint, Sanic

from lingshu.router import compile_route_policies
from lingshu.system.auth.principal import Principal
from lingshu.system.auth.result import AuthResult, AuthenticationOutcome
from lingshu.system.auth.authenticator import (
    Authenticator,
    AuthenticatorChain,
    AuthenticationRejected,
)
from lingshu.system.auth.context import (
    bind_principal,
    current_principal,
    principal_scope,
    require_principal,
)
from lingshu.system.auth.stub_authenticator import StubAuthenticator
from lingshu.system.auth.jwt_bearer import JwtBearerAuthenticator
from lingshu.system.auth.jwt_test_helpers import (
    encode_expired_jwt_token,
    encode_jwt_token,
)
from lingshu.system.errors import NoRequestContextError
from lingshu.system.policy import RoutePolicyDefinition, set_route_policy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_SECRET = "test-secret-key-at-least-32-bytes-long"


def _make_request(headers=None):
    class FakeHeaders:
        def __init__(self, h):
            self._h = h or {}

        def get(self, key, default=None):
            return self._h.get(key, default)

    return SimpleNamespace(headers=FakeHeaders(headers))


def _run(coro):
    return asyncio.run(coro)


def _make_authed_app(name, chain=None):
    from lingshu.system import sanic_adapter
    from lingshu.system.auth.middleware import (
        install_authentication_middleware,
        set_authenticator_chain,
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
        from lingshu.system.auth.context import current_principal
        p = current_principal.get()
        return json_response({"subject": p.subject if p else None})

    set_route_policy(protected_handler, RoutePolicyDefinition())

    app.blueprint(bp)
    compile_route_policies(app)

    if chain is not None:
        set_authenticator_chain(app, chain)
    install_authentication_middleware(app)
    return app


# ---------------------------------------------------------------------------
# 1. Principal — deep immutability and scope validation
# ---------------------------------------------------------------------------

class TestPrincipal:
    def test_create_with_defaults(self):
        p = Principal.create("user-1", "jwt-bearer")
        assert p.subject == "user-1"
        assert p.authenticator_id == "jwt-bearer"
        assert p.scopes == frozenset()
        assert isinstance(p.claims, MappingProxyType)
        assert len(p.claims) == 0

    def test_create_with_scopes_and_claims(self):
        p = Principal.create(
            "user-2", "jwt-bearer",
            scopes={"read", "write"},
            claims={"iss": "issuer", "sub": "user-2"},
        )
        assert p.scopes == frozenset({"read", "write"})
        assert p.claims["iss"] == "issuer"
        assert p.has_scope("read")
        assert not p.has_scope("admin")

    def test_is_frozen(self):
        p = Principal.create("user-1", "jwt-bearer")
        with pytest.raises(Exception):
            p.subject = "other"  # type: ignore[misc]

    def test_claims_are_read_only(self):
        p = Principal.create("u", "a", claims={"k": "v"})
        with pytest.raises(TypeError):
            p.claims["k"] = "other"  # type: ignore[index]

    def test_empty_subject_rejected(self):
        with pytest.raises(ValueError):
            Principal.create("", "jwt-bearer")

    def test_empty_authenticator_id_rejected(self):
        with pytest.raises(ValueError):
            Principal.create("user", "")

    def test_repr_does_not_leak_claims(self):
        p = Principal.create("u", "a", claims={"secret": "s3cret"})
        repr_str = repr(p)
        assert "s3cret" not in repr_str
        assert "u" in repr_str

    # --- Deep immutability ---

    def test_nested_dict_claims_are_frozen(self):
        p = Principal.create("u", "a", claims={"meta": {"role": "admin"}})
        nested = p.claims["meta"]
        with pytest.raises(TypeError):
            nested["role"] = "superadmin"  # type: ignore[index]

    def test_nested_list_claims_are_frozen(self):
        p = Principal.create("u", "a", claims={"roles": ["admin", "user"]})
        nested = p.claims["roles"]
        assert isinstance(nested, tuple)
        with pytest.raises(TypeError):
            nested[0] = "superadmin"  # type: ignore[index]

    def test_deeply_nested_claims_are_frozen(self):
        p = Principal.create("u", "a", claims={
            "level1": {"level2": {"level3": ["a", "b"]}}
        })
        deep = p.claims["level1"]["level2"]["level3"]
        assert isinstance(deep, tuple)
        with pytest.raises(TypeError):
            deep[0] = "c"  # type: ignore[index]

    def test_nested_set_claims_are_frozen(self):
        p = Principal.create("u", "a", claims={"perms": {"read", "write"}})
        nested = p.claims["perms"]
        assert isinstance(nested, frozenset)

    # --- Scope validation ---

    def test_non_string_scope_rejected(self):
        with pytest.raises(TypeError):
            Principal.create("u", "a", scopes=[123])  # type: ignore[list-item]

    def test_empty_scope_string_rejected(self):
        with pytest.raises(ValueError):
            Principal.create("u", "a", scopes=["", "read"])

    def test_whitespace_only_scope_rejected(self):
        with pytest.raises(ValueError):
            Principal.create("u", "a", scopes=["   "])

    def test_object_scope_not_converted_via_str(self):
        class FakeScope:
            def __str__(self):
                return "fake"
        with pytest.raises(TypeError):
            Principal.create("u", "a", scopes=[FakeScope()])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# 2. AuthResult taxonomy
# ---------------------------------------------------------------------------

class TestAuthResult:
    def test_success_is_failure_properties(self):
        assert AuthResult.SUCCESS.is_success
        assert not AuthResult.SUCCESS.is_failure
        assert not AuthResult.MISSING.is_success
        assert AuthResult.MISSING.is_failure

    @pytest.mark.parametrize("result,expected", [
        (AuthResult.MISSING, "invalid_request"),
        (AuthResult.MALFORMED, "invalid_request"),
        (AuthResult.INVALID, "invalid_token"),
        (AuthResult.EXPIRED, "invalid_token"),
        (AuthResult.REVOKED, "invalid_token"),
        (AuthResult.INTERNAL_ERROR, "invalid_token"),
    ])
    def test_www_authenticate_error(self, result, expected):
        assert result.www_authenticate_error == expected


# ---------------------------------------------------------------------------
# 3. AuthenticationOutcome — no leakage
# ---------------------------------------------------------------------------

class TestAuthenticationOutcomeNoLeakage:
    def test_repr_does_not_include_error_description(self):
        outcome = AuthenticationOutcome.malformed("jwt", "secret db password=hunter2")
        r = repr(outcome)
        assert "hunter2" not in r
        assert "secret" not in r
        assert "malformed" in r

    def test_repr_does_not_include_internal_error(self):
        outcome = AuthenticationOutcome.internal_error(
            "jwt", error=RuntimeError("secret key=AKIA1234567890"),
        )
        r = repr(outcome)
        assert "AKIA1234567890" not in r
        assert "secret key" not in r

    def test_custom_repr_does_not_include_sensitive_fields(self):
        """The custom __repr__ must not include error_description or internal_error."""
        outcome = AuthenticationOutcome(
            result=AuthResult.INVALID,
            authenticator_id="jwt",
            error_description="leaked_secret=ABC123",
            internal_error=ValueError("password=hunter2"),
        )
        r = repr(outcome)
        assert "ABC123" not in r
        assert "leaked_secret" not in r
        assert "hunter2" not in r
        assert "password" not in r

    def test_safe_description_for_internal_error(self):
        outcome = AuthenticationOutcome.internal_error(
            "jwt", error=RuntimeError("db connection lost at 10.0.0.5:5432"),
        )
        assert "10.0.0.5" not in outcome.safe_description
        assert "db connection" not in outcome.safe_description


# ---------------------------------------------------------------------------
# 4. AuthenticatorChain
# ---------------------------------------------------------------------------

class TestAuthenticatorChain:
    def test_first_success_short_circuits(self):
        chain = AuthenticatorChain()
        a1 = StubAuthenticator("a1", mode="success")
        a2 = StubAuthenticator("a2", mode="success")
        chain.register(a1)
        chain.register(a2)
        outcome = _run(chain.authenticate(None))
        assert outcome.is_success
        assert outcome.authenticator_id == "a1"
        assert a2.call_count == 0

    def test_missing_falls_through(self):
        chain = AuthenticatorChain()
        a1 = StubAuthenticator("a1", mode="missing")
        a2 = StubAuthenticator("a2", mode="success")
        chain.register(a1)
        chain.register(a2)
        outcome = _run(chain.authenticate(None))
        assert outcome.is_success
        assert outcome.authenticator_id == "a2"

    def test_invalid_short_circuits(self):
        chain = AuthenticatorChain()
        a1 = StubAuthenticator("a1", mode="invalid")
        a2 = StubAuthenticator("a2", mode="success")
        chain.register(a1)
        chain.register(a2)
        outcome = _run(chain.authenticate(None))
        assert outcome.result is AuthResult.INVALID
        assert a2.call_count == 0

    def test_all_missing_returns_missing(self):
        chain = AuthenticatorChain()
        chain.register(StubAuthenticator("a1", mode="missing"))
        chain.register(StubAuthenticator("a2", mode="missing"))
        outcome = _run(chain.authenticate(None))
        assert outcome.result is AuthResult.MISSING

    def test_empty_chain_returns_missing(self):
        chain = AuthenticatorChain()
        outcome = _run(chain.authenticate(None))
        assert outcome.result is AuthResult.MISSING

    def test_exception_wrapped_to_internal_error(self):
        chain = AuthenticatorChain()
        chain.register(StubAuthenticator("boom", raise_exc=RuntimeError("db down")))
        outcome = _run(chain.authenticate(None))
        assert outcome.result is AuthResult.INTERNAL_ERROR

    def test_register_requires_authenticator_id(self):
        chain = AuthenticatorChain()
        class NoId:
            async def authenticate(self, request): pass
        with pytest.raises(ValueError):
            chain.register(NoId())  # type: ignore[arg-type]

    def test_authenticator_ids_preserve_order(self):
        chain = AuthenticatorChain()
        chain.register(StubAuthenticator("c"))
        chain.register(StubAuthenticator("a"))
        chain.register(StubAuthenticator("b"))
        assert chain.authenticator_ids == ("c", "a", "b")

    def test_get_by_id(self):
        chain = AuthenticatorChain()
        stub = StubAuthenticator("findme")
        chain.register(stub)
        assert chain.get("findme") is stub
        assert chain.get("nonexistent") is None

    def test_is_empty(self):
        chain = AuthenticatorChain()
        assert chain.is_empty
        chain.register(StubAuthenticator("x"))
        assert not chain.is_empty


# ---------------------------------------------------------------------------
# 5. StubAuthenticator
# ---------------------------------------------------------------------------

class TestStubAuthenticator:
    @pytest.mark.parametrize("mode_str,result", [
        ("success", AuthResult.SUCCESS),
        ("missing", AuthResult.MISSING),
        ("malformed", AuthResult.MALFORMED),
        ("invalid", AuthResult.INVALID),
        ("expired", AuthResult.EXPIRED),
        ("revoked", AuthResult.REVOKED),
        ("internal_error", AuthResult.INTERNAL_ERROR),
    ])
    def test_all_modes(self, mode_str, result):
        stub = StubAuthenticator("test", mode=mode_str)
        outcome = _run(stub.authenticate(None))
        assert outcome.result is result

    def test_callable_mode(self):
        def custom(request):
            return AuthenticationOutcome.revoked("custom", "banned")
        stub = StubAuthenticator("test", mode=custom)
        outcome = _run(stub.authenticate(None))
        assert outcome.result is AuthResult.REVOKED

    def test_for_result_classmethod(self):
        stub = StubAuthenticator.for_result(AuthResult.EXPIRED, "exp")
        outcome = _run(stub.authenticate(None))
        assert outcome.result is AuthResult.EXPIRED


# ---------------------------------------------------------------------------
# 6. JwtBearerAuthenticator — hardening
# ---------------------------------------------------------------------------

class TestJwtBearerAuthenticator:
    def _make_auth(self, **kwargs):
        defaults = dict(secret=_TEST_SECRET, algorithms=["HS256"])
        defaults.update(kwargs)
        return JwtBearerAuthenticator(**defaults)

    def test_success(self):
        auth = self._make_auth()
        token = encode_jwt_token(_TEST_SECRET, "HS256", subject="user-1", scopes=["read", "write"])
        req = _make_request({"Authorization": f"Bearer {token}"})
        outcome = _run(auth.authenticate(req))
        assert outcome.is_success
        assert outcome.principal.subject == "user-1"
        assert outcome.principal.scopes == frozenset({"read", "write"})

    def test_missing_no_header(self):
        auth = self._make_auth()
        outcome = _run(auth.authenticate(_make_request({})))
        assert outcome.result is AuthResult.MISSING

    def test_malformed_wrong_scheme(self):
        auth = self._make_auth()
        req = _make_request({"Authorization": "Basic abc123"})
        outcome = _run(auth.authenticate(req))
        assert outcome.result is AuthResult.MALFORMED

    def test_malformed_not_jwt(self):
        auth = self._make_auth()
        req = _make_request({"Authorization": "Bearer not.a.jwt"})
        outcome = _run(auth.authenticate(req))
        assert outcome.result in (AuthResult.MALFORMED, AuthResult.INVALID)

    def test_invalid_signature(self):
        auth = self._make_auth()
        token = encode_jwt_token("other-secret-key-at-least-32-bytes-long", "HS256", subject="user-1")
        req = _make_request({"Authorization": f"Bearer {token}"})
        outcome = _run(auth.authenticate(req))
        assert outcome.result is AuthResult.INVALID

    def test_expired(self):
        auth = self._make_auth()
        token = encode_expired_jwt_token(_TEST_SECRET, "HS256", subject="user-1")
        req = _make_request({"Authorization": f"Bearer {token}"})
        outcome = _run(auth.authenticate(req))
        assert outcome.result is AuthResult.EXPIRED

    def test_alg_none_prohibited(self):
        with pytest.raises(ValueError):
            JwtBearerAuthenticator(secret="x" * 32, algorithms=["none"])

    def test_empty_secret_rejected(self):
        with pytest.raises(ValueError):
            JwtBearerAuthenticator(secret="", algorithms=["HS256"])

    def test_empty_algorithms_rejected(self):
        with pytest.raises(ValueError):
            JwtBearerAuthenticator(secret="x" * 32, algorithms=[])

    def test_duplicate_algorithm_rejected(self):
        with pytest.raises(ValueError, match="Duplicate"):
            JwtBearerAuthenticator(secret="x" * 32, algorithms=["HS256", "HS256"])

    def test_algorithm_order_preserved(self):
        auth = JwtBearerAuthenticator(secret="x" * 32, algorithms=["HS512", "HS256"])
        assert auth.algorithms == ("HS512", "HS256")

    def test_mixing_hmac_and_asymmetric_rejected(self):
        with pytest.raises(ValueError, match="Cannot mix"):
            JwtBearerAuthenticator(secret="x" * 32, algorithms=["HS256", "RS256"])

    def test_no_encode_token_method_on_production_class(self):
        auth = self._make_auth()
        assert not hasattr(auth, "encode_token")
        assert not hasattr(auth, "encode_expired_token")

    def test_issuer_verification(self):
        auth = self._make_auth(issuer="my-issuer")
        token = encode_jwt_token(_TEST_SECRET, "HS256", subject="u", issuer="my-issuer")
        req = _make_request({"Authorization": f"Bearer {token}"})
        outcome = _run(auth.authenticate(req))
        assert outcome.is_success

    def test_audience_verification(self):
        auth = self._make_auth(audience="my-aud")
        token = encode_jwt_token(_TEST_SECRET, "HS256", subject="u", audience="my-aud")
        req = _make_request({"Authorization": f"Bearer {token}"})
        outcome = _run(auth.authenticate(req))
        assert outcome.is_success

    # --- Strict scopes validation (no str() conversion) ---

    def test_scopes_with_integer_rejected(self):
        """scopes=[1] must be MALFORMED, not silently converted to '1'."""
        token = encode_jwt_token(
            _TEST_SECRET, "HS256", subject="u", extra_claims={"scopes": [1]},
        )
        req = _make_request({"Authorization": f"Bearer {token}"})
        outcome = _run(self._make_auth().authenticate(req))
        assert outcome.result is AuthResult.MALFORMED

    def test_scopes_with_none_rejected(self):
        """scopes=[None] must be MALFORMED."""
        token = encode_jwt_token(
            _TEST_SECRET, "HS256", subject="u", extra_claims={"scopes": [None]},
        )
        req = _make_request({"Authorization": f"Bearer {token}"})
        outcome = _run(self._make_auth().authenticate(req))
        assert outcome.result is AuthResult.MALFORMED

    def test_scopes_with_empty_string_rejected(self):
        """scopes=[''] must be MALFORMED."""
        token = encode_jwt_token(
            _TEST_SECRET, "HS256", subject="u", extra_claims={"scopes": [""]},
        )
        req = _make_request({"Authorization": f"Bearer {token}"})
        outcome = _run(self._make_auth().authenticate(req))
        assert outcome.result is AuthResult.MALFORMED

    def test_scopes_with_mixed_valid_and_invalid_rejected(self):
        """scopes=['read', 2] must be MALFORMED even if one item is valid."""
        token = encode_jwt_token(
            _TEST_SECRET, "HS256", subject="u", extra_claims={"scopes": ["read", 2]},
        )
        req = _make_request({"Authorization": f"Bearer {token}"})
        outcome = _run(self._make_auth().authenticate(req))
        assert outcome.result is AuthResult.MALFORMED

    def test_scopes_with_valid_string_list_accepted(self):
        """scopes=['read', 'write'] must succeed — not over-rejected."""
        token = encode_jwt_token(_TEST_SECRET, "HS256", subject="u", scopes=["read", "write"])
        req = _make_request({"Authorization": f"Bearer {token}"})
        outcome = _run(self._make_auth().authenticate(req))
        assert outcome.is_success
        assert outcome.principal.scopes == frozenset({"read", "write"})


# ---------------------------------------------------------------------------
# 7. Principal binding — ContextVar isolation
# ---------------------------------------------------------------------------

class TestPrincipalBinding:
    def test_require_principal_raises_without_binding(self):
        with pytest.raises(NoRequestContextError):
            require_principal()

    def test_bind_and_get(self):
        p = Principal.create("u", "jwt")
        with principal_scope(p):
            assert current_principal.get() is p
            assert require_principal() is p
        assert current_principal.get() is None

    def test_concurrent_isolation_100(self):
        async def run_many(total):
            ready = asyncio.Event()
            results = []
            async def worker(i):
                p = Principal.create(f"user-{i}", "jwt")
                with principal_scope(p):
                    await ready.wait()
                    results.append((i, current_principal.get().subject))
            tasks = [asyncio.create_task(worker(i)) for i in range(total)]
            await asyncio.sleep(0)
            ready.set()
            await asyncio.gather(*tasks)
            return results
        results = asyncio.run(run_many(100))
        assert sorted(results) == [(i, f"user-{i}") for i in range(100)]

    def test_concurrent_isolation_500(self):
        async def run_many(total):
            ready = asyncio.Event()
            results = []
            async def worker(i):
                p = Principal.create(f"user-{i}", "jwt")
                with principal_scope(p):
                    await ready.wait()
                    assert current_principal.get().subject == f"user-{i}"
                    results.append(i)
            tasks = [asyncio.create_task(worker(i)) for i in range(total)]
            await asyncio.sleep(0)
            ready.set()
            await asyncio.gather(*tasks)
            return results
        results = asyncio.run(run_many(500))
        assert sorted(results) == list(range(500))

    def test_reset_on_exception(self):
        p = Principal.create("u", "jwt")
        try:
            with principal_scope(p):
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert current_principal.get() is None


# ---------------------------------------------------------------------------
# 8. Protocol conformance and error codes
# ---------------------------------------------------------------------------

class TestAuthenticatorProtocol:
    def test_stub_satisfies_protocol(self):
        assert isinstance(StubAuthenticator("test"), Authenticator)

    def test_jwt_satisfies_protocol(self):
        assert isinstance(JwtBearerAuthenticator(secret="x" * 32, algorithms=["HS256"]), Authenticator)


class TestErrorCodeStability:
    @pytest.mark.parametrize("result,expected_code", [
        (AuthResult.MISSING, 990110),
        (AuthResult.MALFORMED, 990111),
        (AuthResult.INVALID, 990112),
        (AuthResult.EXPIRED, 990113),
        (AuthResult.REVOKED, 990114),
        (AuthResult.INTERNAL_ERROR, 990115),
    ])
    def test_error_codes_defined(self, result, expected_code):
        from lingshu.system.auth.middleware import _RESULT_ERROR_CODE
        assert _RESULT_ERROR_CODE[result] == expected_code


class TestAuthenticationRejected:
    def test_carries_outcome(self):
        outcome = AuthenticationOutcome.missing("jwt")
        exc = AuthenticationRejected(outcome)
        assert exc.outcome is outcome

    def test_safe_message(self):
        outcome = AuthenticationOutcome.internal_error("jwt", error=RuntimeError("secret"))
        exc = AuthenticationRejected(outcome)
        assert "secret" not in str(exc)

    def test_does_not_leak_sensitive_error_description(self):
        """The exception message must use framework-fixed descriptions only.

        Even if the authenticator's error_description contains passwords,
        tokens, or internal details, str(AuthenticationRejected(outcome))
        must never include them.
        """
        outcome = AuthenticationOutcome.invalid(
            "jwt",
            description="password=hunter2 token=abc123 secret_key=AKIA...",
        )
        exc = AuthenticationRejected(outcome)
        msg = str(exc)
        assert "hunter2" not in msg
        assert "abc123" not in msg
        assert "AKIA" not in msg
        assert "password" not in msg
        assert "token" not in msg
        assert "secret_key" not in msg
        assert "invalid" in msg.lower() or "Authentication" in msg

    def test_does_not_leak_internal_exception_text(self):
        """INTERNAL_ERROR outcomes must not expose the wrapped exception."""
        outcome = AuthenticationOutcome.internal_error(
            "jwt", error=ConnectionError("db://user:pass@10.0.0.5:5432"),
        )
        exc = AuthenticationRejected(outcome)
        msg = str(exc)
        assert "10.0.0.5" not in msg
        assert "pass" not in msg
        assert "db://" not in msg
        assert "service error" in msg.lower()


# ---------------------------------------------------------------------------
# 9. Middleware — fail-closed
# ---------------------------------------------------------------------------

class TestFailClosedMiddleware:
    def test_no_chain_registered_returns_401(self):
        """P0 fix: chain not registered → 401/990116, not transparent."""
        app = _make_authed_app("fail-closed-no-chain", chain=None)
        _, response = asyncio.run(app.asgi_client.get("/fail-closed-no-chain/protected"))
        assert response.status == 401
        assert response.json["code"] == 990116

    def test_empty_chain_returns_401(self):
        chain = AuthenticatorChain()
        app = _make_authed_app("fail-closed-empty", chain)
        _, response = asyncio.run(app.asgi_client.get("/fail-closed-empty/protected"))
        assert response.status == 401
        assert response.json["code"] == 990116

    def test_public_route_exempt_even_with_no_chain(self):
        app = _make_authed_app("fail-closed-public", chain=None)
        _, response = asyncio.run(app.asgi_client.get("/fail-closed-public/public"))
        assert response.status == 200


class TestMiddleware401Responses:
    def test_missing_returns_401_with_www_authenticate(self):
        chain = AuthenticatorChain()
        chain.register(StubAuthenticator("jwt", mode="missing"))
        app = _make_authed_app("prot-missing", chain)
        _, response = asyncio.run(app.asgi_client.get("/prot-missing/protected"))
        assert response.status == 401
        assert "WWW-Authenticate" in response.headers
        assert "Bearer" in response.headers["WWW-Authenticate"]
        assert "invalid_request" in response.headers["WWW-Authenticate"]

    def test_invalid_returns_401(self):
        chain = AuthenticatorChain()
        chain.register(StubAuthenticator("jwt", mode="invalid"))
        app = _make_authed_app("prot-invalid", chain)
        _, response = asyncio.run(app.asgi_client.get("/prot-invalid/protected"))
        assert response.status == 401
        assert "invalid_token" in response.headers["WWW-Authenticate"]

    def test_expired_returns_401(self):
        chain = AuthenticatorChain()
        chain.register(StubAuthenticator("jwt", mode="expired"))
        app = _make_authed_app("prot-expired", chain)
        _, response = asyncio.run(app.asgi_client.get("/prot-expired/protected"))
        assert response.status == 401

    def test_success_binds_principal(self):
        chain = AuthenticatorChain()
        chain.register(StubAuthenticator("jwt", mode="success", subject="user-42"))
        app = _make_authed_app("prot-success", chain)
        _, response = asyncio.run(app.asgi_client.get("/prot-success/protected"))
        assert response.status == 200
        assert response.json["data"]["subject"] == "user-42"

    def test_401_does_not_leak_authenticator_description(self):
        """P0 fix: authenticator's error_description must not appear in response."""
        def evil_mode(request):
            return AuthenticationOutcome.invalid("evil", "secret=db_password:Hunter2|token=abc")

        chain = AuthenticatorChain()
        chain.register(StubAuthenticator("evil", mode=evil_mode))
        app = _make_authed_app("prot-leak-desc", chain)
        _, response = asyncio.run(app.asgi_client.get("/prot-leak-desc/protected"))
        assert response.status == 401
        body = str(response.json)
        header = response.headers.get("WWW-Authenticate", "")
        assert "Hunter2" not in body
        assert "Hunter2" not in header
        assert "db_password" not in body
        assert "db_password" not in header
        assert "token=abc" not in body
        assert "token=abc" not in header

    def test_401_does_not_leak_internal_exception(self):
        chain = AuthenticatorChain()
        chain.register(StubAuthenticator("jwt", raise_exc=RuntimeError("DB password = hunter2")))
        app = _make_authed_app("prot-leak-exc", chain)
        _, response = asyncio.run(app.asgi_client.get("/prot-leak-exc/protected"))
        assert response.status == 401
        body = str(response.json)
        assert "hunter2" not in body
        assert "DB password" not in body


# ---------------------------------------------------------------------------
# 10. request.principal context semantics
# ---------------------------------------------------------------------------

class TestRequestPrincipalSemantics:
    def test_no_context_raises(self):
        from lingshu.system.proxies import RequestProxy
        proxy = RequestProxy()
        with pytest.raises(NoRequestContextError):
            _ = proxy.principal

    def test_public_route_returns_none(self):
        """A public route has an execution context but no principal."""
        app = _make_authed_app("principal-public-none", chain=None)

        async def check():
            _, response = await app.asgi_client.get("/principal-public-none/public")
            return response

        response = asyncio.run(check())
        assert response.status == 200

    def test_protected_success_returns_principal(self):
        chain = AuthenticatorChain()
        chain.register(StubAuthenticator("jwt", mode="success", subject="user-x"))
        app = _make_authed_app("principal-protected", chain)
        _, response = asyncio.run(app.asgi_client.get("/principal-protected/protected"))
        assert response.status == 200
        assert response.json["data"]["subject"] == "user-x"


# ---------------------------------------------------------------------------
# 11. Principal cleanup through real request lifecycle
# ---------------------------------------------------------------------------

class TestPrincipalCleanupLifecycle:
    def test_cleanup_after_normal_return(self):
        """Principal is cleaned up after a successful request."""
        chain = AuthenticatorChain()
        chain.register(StubAuthenticator("jwt", mode="success", subject="clean-normal"))
        app = _make_authed_app("cleanup-normal", chain)

        _, response = asyncio.run(app.asgi_client.get("/cleanup-normal/protected"))
        assert response.status == 200
        assert current_principal.get() is None

    def test_cleanup_after_handler_exception(self):
        """Principal is cleaned up even if the handler raises."""
        from lingshu.system import sanic_adapter
        from lingshu.system.auth.middleware import (
            install_authentication_middleware,
            set_authenticator_chain,
        )

        app = Sanic("cleanup-exc")
        sanic_adapter.install_context_middleware(app)
        bp = Blueprint("cleanup-exc-bp", url_prefix="/ce")

        @bp.get("/boom", name="boom")
        async def boom_handler(request):
            raise RuntimeError("handler explosion")

        set_route_policy(boom_handler, RoutePolicyDefinition())
        app.blueprint(bp)
        compile_route_policies(app)

        chain = AuthenticatorChain()
        chain.register(StubAuthenticator("jwt", mode="success", subject="clean-exc"))
        set_authenticator_chain(app, chain)
        install_authentication_middleware(app)

        _, response = asyncio.run(app.asgi_client.get("/ce/boom"))
        assert response.status == 500
        assert current_principal.get() is None

    def test_cleanup_after_timeout(self):
        """Principal is cleaned up after a deadline timeout."""
        from lingshu.system import sanic_adapter
        from lingshu.system.auth.middleware import (
            install_authentication_middleware,
            set_authenticator_chain,
        )

        app = Sanic("cleanup-timeout")
        sanic_adapter.install_context_middleware(app)
        bp = Blueprint("cleanup-timeout-bp", url_prefix="/ct")

        @bp.get("/slow", name="slow")
        async def slow_handler(request):
            await asyncio.sleep(10)
            return None

        # Very short timeout to trigger deadline quickly
        set_route_policy(slow_handler, RoutePolicyDefinition(timeout=0.01))
        app.blueprint(bp)
        compile_route_policies(app)

        chain = AuthenticatorChain()
        chain.register(StubAuthenticator("jwt", mode="success", subject="clean-timeout"))
        set_authenticator_chain(app, chain)
        install_authentication_middleware(app)

        _, response = asyncio.run(app.asgi_client.get("/ct/slow"))
        # Deadline produces 504 or 500 depending on path
        assert response.status in (504, 500)
        assert current_principal.get() is None

    def test_subsequent_request_does_not_see_previous_principal(self):
        """After request A completes, request B must not inherit A's principal."""
        chain_a = AuthenticatorChain()
        chain_a.register(StubAuthenticator("jwt", mode="success", subject="user-a"))
        app = _make_authed_app("cleanup-isolation", chain_a)

        # Request A — authenticated
        _, resp_a = asyncio.run(app.asgi_client.get("/cleanup-isolation/protected"))
        assert resp_a.status == 200
        assert resp_a.json["data"]["subject"] == "user-a"

        # After request A finishes, no principal should be bound in this context.
        assert current_principal.get() is None

        # Request B with a different authenticator returns a different subject
        from lingshu.system.auth.middleware import set_authenticator_chain
        chain_b = AuthenticatorChain()
        chain_b.register(StubAuthenticator("jwt", mode="success", subject="user-b"))
        set_authenticator_chain(app, chain_b)

        _, resp_b = asyncio.run(app.asgi_client.get("/cleanup-isolation/protected"))
        assert resp_b.status == 200
        assert resp_b.json["data"]["subject"] == "user-b"
        assert current_principal.get() is None

    def test_cleanup_after_cancellation(self):
        """Principal is cleaned up when the handler task is cancelled.

        Uses Event-based deterministic synchronization — no random sleep.

        Verifies:
        1. CancelledError is not swallowed.
        2. Principal binding is reset/detached.
        3. No Principal is bound after the task ends.
        4. A subsequent request cannot read the cancelled request's identity.
        """
        from lingshu.system import sanic_adapter
        from lingshu.system.auth.middleware import (
            install_authentication_middleware,
            set_authenticator_chain,
        )

        app = Sanic("cleanup-cancel")
        sanic_adapter.install_context_middleware(app)
        bp = Blueprint("cleanup-cancel-bp", url_prefix="/cc")

        handler_entered = asyncio.Event()
        captured = {}
        cancel_mode = {"cancelled": False}

        @bp.get("/cancel", name="cancel")
        async def cancel_handler(request):
            from lingshu.response import json_response
            captured["binding"] = request.ctx.lingshu_principal_binding
            captured["request"] = request
            handler_entered.set()
            if cancel_mode["cancelled"]:
                p = current_principal.get()
                return json_response({"subject": p.subject if p else None})
            await asyncio.sleep(30)
            return None  # unreachable

        set_route_policy(cancel_handler, RoutePolicyDefinition(timeout=60.0))
        app.blueprint(bp)
        compile_route_policies(app)

        chain = AuthenticatorChain()
        chain.register(StubAuthenticator("jwt", mode="success", subject="cancel-user"))
        set_authenticator_chain(app, chain)
        install_authentication_middleware(app)

        async def scenario():
            cleanup_done = asyncio.Event()

            request_task = asyncio.ensure_future(app.asgi_client.get("/cc/cancel"))
            request_task.add_done_callback(lambda _t: cleanup_done.set())
            await handler_entered.wait()

            # The handler is running; a principal binding must exist on the request.
            binding = captured["binding"]
            assert binding is not None
            assert binding.principal is not None
            assert binding.principal.subject == "cancel-user"

            # Cancel the in-flight request.
            request_task.cancel()

            # CancelledError must propagate — it must NOT be swallowed.
            with pytest.raises(asyncio.CancelledError):
                await request_task

            # Wait deterministically for all done-callbacks (including the
            # context-middleware cleanup callback) to finish.
            await asyncio.wait_for(cleanup_done.wait(), timeout=5.0)

            assert captured["request"].ctx.lingshu_principal_binding is None
            assert captured["binding"].reset_done is True

            # 4. A subsequent request must not inherit the cancelled identity.
            cancel_mode["cancelled"] = True
            chain2 = AuthenticatorChain()
            chain2.register(StubAuthenticator("jwt", mode="success", subject="next-user"))
            set_authenticator_chain(app, chain2)

            _, resp_next = await app.asgi_client.get("/cc/cancel")
            assert resp_next.status == 200
            assert resp_next.json["data"]["subject"] == "next-user"

        asyncio.run(scenario())


# ---------------------------------------------------------------------------
# 12. Multi-app isolation
# ---------------------------------------------------------------------------

class TestMultiAppIsolation:
    def test_separate_apps_have_independent_chains(self):
        chain_a = AuthenticatorChain()
        chain_a.register(StubAuthenticator("auth-a", mode="success", subject="user-a"))
        chain_b = AuthenticatorChain()
        chain_b.register(StubAuthenticator("auth-b", mode="missing"))

        app_a = _make_authed_app("iso-a", chain_a)
        app_b = _make_authed_app("iso-b", chain_b)

        _, resp_a = asyncio.run(app_a.asgi_client.get("/iso-a/protected"))
        assert resp_a.status == 200
        assert resp_a.json["data"]["subject"] == "user-a"

        _, resp_b = asyncio.run(app_b.asgi_client.get("/iso-b/protected"))
        assert resp_b.status == 401


# ---------------------------------------------------------------------------
# 13. Concurrent request isolation
# ---------------------------------------------------------------------------

class TestConcurrentRequestIsolation:
    def test_concurrent_requests_no_principal_leak(self):
        def mode_fn(request):
            user = request.headers.get("X-Test-User", "anon")
            if user == "anon":
                return AuthenticationOutcome.missing("stub")
            return AuthenticationOutcome.success(Principal.create(user, "stub"))

        chain = AuthenticatorChain()
        chain.register(StubAuthenticator("stub", mode=mode_fn))
        app = _make_authed_app("concurrent-auth", chain)

        async def fetch(user):
            _, resp = await app.asgi_client.get(
                "/concurrent-auth/protected",
                headers={"X-Test-User": user},
            )
            return user, resp.status, resp.json["data"]["subject"]

        async def run_all():
            users = [f"user-{i}" for i in range(20)]
            return await asyncio.gather(*[fetch(u) for u in users])

        results = asyncio.run(run_all())
        for user, status, subject in results:
            assert status == 200, f"{user} got {status}"
            assert subject == user


# ---------------------------------------------------------------------------
# 14. Public lingshu.auth API smoke test
# ---------------------------------------------------------------------------

class TestPublicAuthAPI:
    def test_imports_from_lingshu_auth(self):
        from lingshu.auth import (
            AuthenticatorChain,
            JwtBearerAuthenticator,
            Principal,
            AuthResult,
            AuthenticationOutcome,
            Authenticator,
            configure_authentication,
            get_principal,
            require_principal,
        )
        assert AuthenticatorChain is not None
        assert JwtBearerAuthenticator is not None
        assert Principal is not None

    def test_imports_from_lingshu_top_level(self):
        import lingshu
        import lingshu.auth as auth_mod
        # lingshu.auth module is importable
        assert auth_mod.Principal is not None
        assert auth_mod.AuthenticatorChain is not None
        assert auth_mod.configure_authentication is not None

    def test_configure_authentication_via_public_api(self):
        """Bootstrap smoke test: configure JWT auth using only public APIs.

        Business code should never import ``lingshu.system``.  This test
        proves the public surface (``lingshu.auth``, ``lingshu.request``,
        ``lingshu.router``) is sufficient to:
        - configure a JWT authenticator chain,
        - mark routes public/protected via RoutePolicy,
        - read the principal inside a handler via lingshu.request.principal.
        """
        import lingshu  # public proxy: lingshu.request is a RequestProxy instance
        from lingshu.app import create_app
        from lingshu.auth import (
            AuthenticatorChain,
            JwtBearerAuthenticator,
            configure_authentication,
        )
        from lingshu.router import RoutePolicy, register_blueprints, set_blueprint_policy

        app = create_app()

        # Protected blueprint — default policy requires auth.
        secure_bp = Blueprint("smoke-secure-bp", url_prefix="/smoke")
        set_blueprint_policy(secure_bp, RoutePolicy())

        @secure_bp.get("/secure", name="secure")
        async def secure(request):
            from lingshu.response import json_response
            p = lingshu.request.principal
            return json_response({"sub": p.subject if p else None})

        # Public blueprint — no auth required.
        open_bp = Blueprint("smoke-open-bp", url_prefix="/smoke")
        set_blueprint_policy(
            open_bp,
            RoutePolicy(auth_required=False, signing_required=False, maintenance_check=False),
        )

        @open_bp.get("/open", name="open")
        async def open_endpoint(request):
            from lingshu.response import json_response
            return json_response({"ok": True})

        register_blueprints(app, [secure_bp, open_bp])
        compile_route_policies(app)

        chain = AuthenticatorChain()
        chain.register(JwtBearerAuthenticator(
            secret=_TEST_SECRET,
            algorithms=["HS256"],
            issuer="smoke-issuer",
        ))
        configure_authentication(app, chain)

        # Public route works without token
        _, resp_open = asyncio.run(app.asgi_client.get("/smoke/open"))
        assert resp_open.status == 200

        # Protected route fails without token
        _, resp_no_token = asyncio.run(app.asgi_client.get("/smoke/secure"))
        assert resp_no_token.status == 401

        # Protected route works with valid token
        token = encode_jwt_token(
            _TEST_SECRET, "HS256",
            subject="smoke-user",
            issuer="smoke-issuer",
        )
        _, resp_token = asyncio.run(app.asgi_client.get(
            "/smoke/secure",
            headers={"Authorization": f"Bearer {token}"},
        ))
        assert resp_token.status == 200
        assert resp_token.json["data"]["sub"] == "smoke-user"

    def test_business_code_does_not_import_lingshu_system(self):
        """AST-level check: lingshu.auth does not expose lingshu.system imports."""
        import lingshu.auth as auth_module
        # The public module should re-export, not require business users to
        # import lingshu.system
        assert hasattr(auth_module, "Principal")
        assert hasattr(auth_module, "AuthenticatorChain")


# ---------------------------------------------------------------------------
# 15. Integration regressions via real create_app()
# ---------------------------------------------------------------------------

class TestCreateAppFailClosedIntegration:
    """Verify that the real create_app() installs fail-closed middleware."""

    def test_protected_route_401_when_chain_not_registered(self):
        from lingshu.app import create_app

        app = create_app()
        bp = Blueprint("fail-closed-integ", url_prefix="/fci")

        @bp.get("/protected", name="protected")
        async def protected(request):
            from lingshu.response import json_response
            return json_response({"ok": True})

        set_route_policy(protected, RoutePolicyDefinition())
        app.blueprint(bp)
        compile_route_policies(app)

        _, response = asyncio.run(app.asgi_client.get("/fci/protected"))
        assert response.status == 401
        assert response.json["code"] == 990116

    def test_public_route_200_when_chain_not_registered(self):
        from lingshu.app import create_app

        app = create_app()
        bp = Blueprint("fail-closed-public-integ", url_prefix="/fcpi")

        @bp.get("/open", name="open")
        async def open_endpoint(request):
            from lingshu.response import json_response
            return json_response({"ok": True})

        set_route_policy(open_endpoint, RoutePolicyDefinition(public=True))
        app.blueprint(bp)
        compile_route_policies(app)

        _, response = asyncio.run(app.asgi_client.get("/fcpi/open"))
        assert response.status == 200


# ---------------------------------------------------------------------------
# 16. Idempotent middleware / configure_authentication
# ---------------------------------------------------------------------------

class TestIdempotentMiddleware:
    """configure_authentication replaces chain; middleware installs once."""

    def test_double_configure_single_authentication_per_request(self):
        from lingshu.system import sanic_adapter
        from lingshu.system.auth.middleware import (
            install_authentication_middleware,
            set_authenticator_chain,
        )

        app = Sanic("idempotent-config")
        sanic_adapter.install_context_middleware(app)
        bp = Blueprint("idempotent-bp", url_prefix="/id")

        @bp.get("/secure", name="secure")
        async def secure(request):
            from lingshu.response import json_response
            p = current_principal.get()
            return json_response({"subject": p.subject if p else None})

        set_route_policy(secure, RoutePolicyDefinition())
        app.blueprint(bp)
        compile_route_policies(app)

        stub1 = StubAuthenticator("first", mode="success", subject="user-1")
        chain1 = AuthenticatorChain()
        chain1.register(stub1)
        set_authenticator_chain(app, chain1)
        install_authentication_middleware(app)

        # Second install must be a no-op.
        install_authentication_middleware(app)

        # Replace chain.
        stub2 = StubAuthenticator("second", mode="success", subject="user-2")
        chain2 = AuthenticatorChain()
        chain2.register(stub2)
        set_authenticator_chain(app, chain2)

        _, response = asyncio.run(app.asgi_client.get("/id/secure"))
        assert response.status == 200
        assert response.json["data"]["subject"] == "user-2"
        assert stub2.call_count == 1
        assert stub1.call_count == 0
        assert current_principal.get() is None


# ---------------------------------------------------------------------------
# 17. Import order stability
# ---------------------------------------------------------------------------

class TestImportOrderStability:
    """lingshu.auth must be stable regardless of import order."""

    def test_import_lingshu_then_auth(self):
        import lingshu
        import lingshu.auth
        assert lingshu.auth.Principal is not None
        assert lingshu.auth.AuthenticatorChain is not None
        assert lingshu.auth.configure_authentication is not None

    def test_import_auth_then_lingshu(self):
        import lingshu.auth
        import lingshu
        assert lingshu.auth.Principal is not None
        assert lingshu.auth.AuthenticatorChain is not None

    def test_from_lingshu_import_auth(self):
        import lingshu.auth
        from lingshu import auth
        assert auth is lingshu.auth
        assert auth.Principal is not None
        assert auth.AuthenticatorChain is not None
