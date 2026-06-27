"""Phase C2.1 authentication foundation tests.

Covers:
- Principal immutability and validation
- AuthResult taxonomy and WWW-Authenticate mapping
- AuthenticationOutcome factory methods and safe_description
- AuthenticatorChain registration order and short-circuit semantics
- StubAuthenticator deterministic modes
- JwtBearerAuthenticator: success, missing, malformed, invalid, expired, alg=none
- Principal binding / ContextVar isolation / cleanup
- public route exemption
- protected route 401 with stable error code and WWW-Authenticate
- concurrent isolation
- multi-app isolation
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
from lingshu.system.errors import NoRequestContextError
from lingshu.system.policy import RoutePolicyDefinition, set_route_policy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(headers: dict[str, str] | None = None):
    class FakeHeaders:
        def __init__(self, h):
            self._h = h or {}

        def get(self, key, default=None):
            return self._h.get(key, default)

    return SimpleNamespace(headers=FakeHeaders(headers))


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Principal
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


# ---------------------------------------------------------------------------
# AuthResult taxonomy
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
# AuthenticationOutcome
# ---------------------------------------------------------------------------

class TestAuthenticationOutcome:
    def test_success_factory(self):
        p = Principal.create("u", "jwt")
        outcome = AuthenticationOutcome.success(p)
        assert outcome.is_success
        assert outcome.principal is p
        assert outcome.authenticator_id == "jwt"

    def test_missing_factory(self):
        outcome = AuthenticationOutcome.missing("jwt")
        assert outcome.result is AuthResult.MISSING
        assert outcome.principal is None

    def test_malformed_factory(self):
        outcome = AuthenticationOutcome.malformed("jwt", "bad format")
        assert outcome.result is AuthResult.MALFORMED
        assert "bad format" in outcome.error_description

    def test_internal_error_safe_description(self):
        outcome = AuthenticationOutcome.internal_error(
            "jwt", error=RuntimeError("secret key leaked"),
        )
        assert outcome.result is AuthResult.INTERNAL_ERROR
        assert "secret" not in outcome.safe_description
        assert outcome.internal_error is not None
        assert "secret" in str(outcome.internal_error)


# ---------------------------------------------------------------------------
# AuthenticatorChain
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
        assert a1.call_count == 1
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
        assert a1.call_count == 1
        assert a2.call_count == 1

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
        assert "db down" not in outcome.safe_description

    def test_register_requires_authenticator_id(self):
        chain = AuthenticatorChain()

        class NoId:
            async def authenticate(self, request):
                pass

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
# StubAuthenticator
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
# JwtBearerAuthenticator
# ---------------------------------------------------------------------------

class TestJwtBearerAuthenticator:
    def _make_auth(self, **kwargs):
        defaults = dict(secret="test-secret-key", algorithms=["HS256"])
        defaults.update(kwargs)
        return JwtBearerAuthenticator(**defaults)

    def test_success(self):
        auth = self._make_auth()
        token = auth.encode_token(subject="user-1", scopes=["read", "write"])
        req = _make_request({"Authorization": f"Bearer {token}"})
        outcome = _run(auth.authenticate(req))
        assert outcome.is_success
        assert outcome.principal.subject == "user-1"
        assert outcome.principal.scopes == frozenset({"read", "write"})
        assert outcome.principal.authenticator_id == "jwt-bearer"

    def test_missing_no_header(self):
        auth = self._make_auth()
        req = _make_request({})
        outcome = _run(auth.authenticate(req))
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
        wrong_auth = JwtBearerAuthenticator(secret="other-secret", algorithms=["HS256"])
        token = wrong_auth.encode_token(subject="user-1")
        req = _make_request({"Authorization": f"Bearer {token}"})
        outcome = _run(auth.authenticate(req))
        assert outcome.result is AuthResult.INVALID

    def test_expired(self):
        auth = self._make_auth()
        token = auth.encode_expired_token(subject="user-1")
        req = _make_request({"Authorization": f"Bearer {token}"})
        outcome = _run(auth.authenticate(req))
        assert outcome.result is AuthResult.EXPIRED

    def test_alg_none_prohibited_in_config(self):
        with pytest.raises(ValueError):
            JwtBearerAuthenticator(secret="x", algorithms=["none"])

    def test_empty_secret_rejected(self):
        with pytest.raises(ValueError):
            JwtBearerAuthenticator(secret="", algorithms=["HS256"])

    def test_empty_algorithms_rejected(self):
        with pytest.raises(ValueError):
            JwtBearerAuthenticator(secret="x", algorithms=[])

    def test_issuer_verification(self):
        auth = self._make_auth(issuer="my-issuer")
        token = auth.encode_token(subject="u", issuer="my-issuer")
        req = _make_request({"Authorization": f"Bearer {token}"})
        outcome = _run(auth.authenticate(req))
        assert outcome.is_success

    def test_audience_verification(self):
        auth = self._make_auth(audience="my-aud")
        token = auth.encode_token(subject="u", audience="my-aud")
        req = _make_request({"Authorization": f"Bearer {token}"})
        outcome = _run(auth.authenticate(req))
        assert outcome.is_success

    def test_scopes_as_space_separated_string(self):
        import jwt as _jwt
        import time as _time

        auth = self._make_auth()
        payload = {
            "sub": "u1",
            "exp": int(_time.time()) + 3600,
            "scopes": "read write admin",
        }
        token = _jwt.encode(payload, "test-secret-key", algorithm="HS256")
        req = _make_request({"Authorization": f"Bearer {token}"})
        outcome = _run(auth.authenticate(req))
        assert outcome.is_success
        assert outcome.principal.scopes == frozenset({"read", "write", "admin"})


# ---------------------------------------------------------------------------
# Principal binding / ContextVar isolation
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
# Authenticator Protocol conformance
# ---------------------------------------------------------------------------

class TestAuthenticatorProtocol:
    def test_stub_satisfies_protocol(self):
        stub = StubAuthenticator("test")
        assert isinstance(stub, Authenticator)

    def test_jwt_satisfies_protocol(self):
        auth = JwtBearerAuthenticator(secret="x", algorithms=["HS256"])
        assert isinstance(auth, Authenticator)


# ---------------------------------------------------------------------------
# Error code stability
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# AuthenticationRejected bridge exception
# ---------------------------------------------------------------------------

class TestAuthenticationRejected:
    def test_carries_outcome(self):
        outcome = AuthenticationOutcome.missing("jwt")
        exc = AuthenticationRejected(outcome)
        assert exc.outcome is outcome

    def test_safe_message(self):
        outcome = AuthenticationOutcome.internal_error("jwt", error=RuntimeError("secret"))
        exc = AuthenticationRejected(outcome)
        assert "secret" not in str(exc)


# ---------------------------------------------------------------------------
# Middleware integration via ASGI client
# ---------------------------------------------------------------------------

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

    # auth_required defaults to True when public is not set
    set_route_policy(protected_handler, RoutePolicyDefinition())

    app.blueprint(bp)
    compile_route_policies(app)

    if chain is not None:
        set_authenticator_chain(app, chain)
    install_authentication_middleware(app)
    return app


class TestPublicRouteExempt:
    def test_public_route_exempt_even_with_empty_chain(self):
        chain = AuthenticatorChain()
        app = _make_authed_app("pub-exempt", chain)

        _, response = asyncio.run(app.asgi_client.get("/pub-exempt/public"))
        assert response.status == 200


class TestProtectedRoute401:
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

    def test_no_chain_registered_is_transparent(self):
        app = _make_authed_app("prot-no-chain", chain=None)

        _, response = asyncio.run(app.asgi_client.get("/prot-no-chain/protected"))
        assert response.status == 200

    def test_empty_chain_returns_scheme_not_registered_401(self):
        chain = AuthenticatorChain()
        app = _make_authed_app("prot-empty-chain", chain)

        _, response = asyncio.run(app.asgi_client.get("/prot-empty-chain/protected"))
        assert response.status == 401

    def test_401_does_not_leak_internal_details(self):
        chain = AuthenticatorChain()
        chain.register(StubAuthenticator("jwt", raise_exc=RuntimeError("DB password = hunter2")))
        app = _make_authed_app("prot-leak", chain)

        _, response = asyncio.run(app.asgi_client.get("/prot-leak/protected"))
        assert response.status == 401
        body_text = str(response.json)
        assert "hunter2" not in body_text
        assert "DB password" not in body_text


# ---------------------------------------------------------------------------
# Multi-app isolation
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
# Concurrent request isolation through full middleware
# ---------------------------------------------------------------------------

class TestConcurrentRequestIsolation:
    def test_concurrent_requests_no_principal_leak(self):
        def mode_fn(request):
            user = request.headers.get("X-Test-User", "anon")
            if user == "anon":
                return AuthenticationOutcome.missing("stub")
            return AuthenticationOutcome.success(
                Principal.create(user, "stub")
            )

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
            tasks = [fetch(u) for u in users]
            return await asyncio.gather(*tasks)

        results = asyncio.run(run_all())
        for user, status, subject in results:
            assert status == 200, f"{user} got {status}"
            assert subject == user, f"Expected {user}, got {subject}"
