from __future__ import annotations

from lingshu.system.auth.principal import Principal
from lingshu.system.auth.result import AuthenticationOutcome, AuthResult


class StubAuthenticator:
    """Deterministic authenticator for test suites.

    This authenticator is NOT for production use.  It allows tests to simulate
    any AuthResult without depending on JWT or external services.

    Usage::

        auth = StubAuthenticator("test-auth", mode="success", subject="user-1")
        chain = AuthenticatorChain()
        chain.register(auth)
        outcome = await chain.authenticate(request)

    For multi-step scenarios, you can set ``mode`` to a callable that receives
    the request and returns an AuthenticationOutcome.
    """

    authenticator_id = "stub"

    def __init__(
        self,
        authenticator_id: str = "stub",
        *,
        mode: str = "success",
        subject: str = "test-subject",
        scopes: frozenset[str] | set[str] | tuple[str, ...] | None = None,
        claims: dict | None = None,
        raise_exc: BaseException | None = None,
    ):
        self.authenticator_id = authenticator_id
        self._mode = mode
        self._subject = subject
        self._scopes = scopes
        self._claims = claims
        self._raise_exc = raise_exc
        self.call_count = 0

    async def authenticate(self, request) -> AuthenticationOutcome:
        self.call_count += 1

        if self._raise_exc is not None:
            raise self._raise_exc

        mode = self._mode

        # Callable mode: delegate entirely
        if callable(mode):
            return mode(request)

        if mode == AuthResult.SUCCESS or mode == "success":
            principal = Principal.create(
                subject=self._subject,
                authenticator_id=self.authenticator_id,
                scopes=self._scopes,
                claims=self._claims,
            )
            return AuthenticationOutcome.success(principal)

        if mode == AuthResult.MISSING or mode == "missing":
            return AuthenticationOutcome.missing(self.authenticator_id)

        if mode == AuthResult.MALFORMED or mode == "malformed":
            return AuthenticationOutcome.malformed(self.authenticator_id, "Stub: malformed credential")

        if mode == AuthResult.INVALID or mode == "invalid":
            return AuthenticationOutcome.invalid(self.authenticator_id, "Stub: invalid credential")

        if mode == AuthResult.EXPIRED or mode == "expired":
            return AuthenticationOutcome.expired(self.authenticator_id, "Stub: expired credential")

        if mode == AuthResult.REVOKED or mode == "revoked":
            return AuthenticationOutcome.revoked(self.authenticator_id, "Stub: revoked credential")

        if mode == AuthResult.INTERNAL_ERROR or mode == "internal_error":
            return AuthenticationOutcome.internal_error(
                self.authenticator_id,
                error=RuntimeError("Stub: simulated internal error"),
            )

        raise ValueError(f"Unknown StubAuthenticator mode: {mode!r}")

    @classmethod
    def for_result(
        cls,
        result: AuthResult | str,
        authenticator_id: str = "stub",
        **kwargs,
    ) -> StubAuthenticator:
        return cls(authenticator_id=authenticator_id, mode=result, **kwargs)
