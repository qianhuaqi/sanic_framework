from __future__ import annotations

from typing import Protocol, runtime_checkable

from lingshu.system.auth.result import AuthenticationOutcome, AuthResult


class AuthenticationRejected(Exception):
    """Raised when authentication fails and the request must be rejected.

    This is the bridge exception used inside the middleware layer.  It carries
    the outcome so the error handler can produce a precise 401 response.
    """

    def __init__(self, outcome: AuthenticationOutcome):
        self.outcome = outcome
        super().__init__(outcome.safe_description)


@runtime_checkable
class Authenticator(Protocol):
    """Protocol for credential verifiers.

    Each authenticator receives the raw Sanic request and returns an
    :class:`AuthenticationOutcome`.  Implementations must:

    - Distinguish MISSING (no credential present) from INVALID/MALFORMED
      (credential present but failed).
    - Never raise an exception for expected failure paths — wrap unexpected
      exceptions into ``AuthResult.INTERNAL_ERROR``.
    - Never leak internal exception text into ``error_description``.
    """

    authenticator_id: str

    async def authenticate(self, request) -> AuthenticationOutcome: ...


class AuthenticatorChain:
    """Ordered registry of authenticators and single-pass executor.

    Semantics:
    - Authenticators are executed in registration order.
    - The first SUCCESS short-circuits the chain.
    - MISSING does NOT short-circuit: a later authenticator may succeed.
    - Any of INVALID, MALFORMED, EXPIRED, REVOKED, or INTERNAL_ERROR
      immediately short-circuits and returns that failure.
    - If all authenticators return MISSING, the overall result is MISSING.

    This ensures that:
    - A request with a malformed Authorization header is rejected even if a
      later authenticator could theoretically accept no credential.
    - A request with no credential at all falls through to MISSING only if no
      authenticator found a present-but-invalid credential.
    """

    def __init__(self):
        self._authenticators: list[Authenticator] = []

    def register(self, authenticator: Authenticator) -> Authenticator:
        if not hasattr(authenticator, "authenticator_id") or not authenticator.authenticator_id:
            raise ValueError("Authenticator must have a non-empty authenticator_id")
        self._authenticators.append(authenticator)
        return authenticator

    def get(self, authenticator_id: str) -> Authenticator | None:
        for auth in self._authenticators:
            if auth.authenticator_id == authenticator_id:
                return auth
        return None

    @property
    def authenticator_ids(self) -> tuple[str, ...]:
        return tuple(auth.authenticator_id for auth in self._authenticators)

    @property
    def is_empty(self) -> bool:
        return len(self._authenticators) == 0

    async def authenticate(self, request) -> AuthenticationOutcome:
        last_outcome: AuthenticationOutcome | None = None

        for authenticator in self._authenticators:
            try:
                outcome = await authenticator.authenticate(request)
            except Exception as exc:
                outcome = AuthenticationOutcome.internal_error(
                    authenticator_id=getattr(authenticator, "authenticator_id", ""),
                    error=exc,
                )

            if outcome.is_success:
                return outcome

            if outcome.result is AuthResult.MISSING:
                last_outcome = outcome
                continue

            # Any non-success, non-missing result short-circuits.
            return outcome

        if last_outcome is not None:
            return last_outcome
        return AuthenticationOutcome.missing()
