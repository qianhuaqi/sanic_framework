from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from lingshu.system.auth.principal import Principal


class AuthResult(str, Enum):
    """Authentication outcome taxonomy.

    Each value maps to a distinct failure mode so that callers can produce
    precise 401 responses and WWW-Authenticate headers.

    Members:
        SUCCESS: Authentication succeeded; a Principal is attached.
        MISSING: No credential was present at all.
        MALFORMED: A credential was present but structurally invalid
            (e.g. wrong Authorization header format, not a JWT).
        INVALID: The credential was structurally valid but failed verification
            (wrong signature, unknown issuer, wrong audience).
        EXPIRED: The credential was valid but has passed its expiry.
        REVOKED: The credential was valid but has been revoked.
        INTERNAL_ERROR: An unexpected internal exception occurred.  The error
            detail must never be returned to the client.
    """

    SUCCESS = "success"
    MISSING = "missing"
    MALFORMED = "malformed"
    INVALID = "invalid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    INTERNAL_ERROR = "internal_error"

    @property
    def is_success(self) -> bool:
        return self is AuthResult.SUCCESS

    @property
    def is_failure(self) -> bool:
        return self is not AuthResult.SUCCESS

    @property
    def www_authenticate_error(self) -> str:
        """RFC 6750 / 7235 error code for WWW-Authenticate header."""
        if self is AuthResult.MISSING:
            return "invalid_request"
        if self is AuthResult.MALFORMED:
            return "invalid_request"
        if self is AuthResult.INVALID:
            return "invalid_token"
        if self is AuthResult.EXPIRED:
            return "invalid_token"
        if self is AuthResult.REVOKED:
            return "invalid_token"
        return "invalid_token"


@dataclass(frozen=True)
class AuthenticationOutcome:
    """The result of an authentication attempt.

    On success, ``principal`` is populated.
    On failure, ``principal`` is ``None`` and ``error_description`` may carry
    a *safe* description suitable for WWW-Authenticate.  The raw exception
    (if any) is accessible only via ``internal_error`` and must never be
    serialised into a client response.
    """

    result: AuthResult
    principal: Principal | None = None
    authenticator_id: str = ""
    error_description: str = ""
    internal_error: BaseException | None = None

    @classmethod
    def success(cls, principal: Principal) -> AuthenticationOutcome:
        return cls(result=AuthResult.SUCCESS, principal=principal, authenticator_id=principal.authenticator_id)

    @classmethod
    def missing(cls, authenticator_id: str = "") -> AuthenticationOutcome:
        return cls(result=AuthResult.MISSING, authenticator_id=authenticator_id)

    @classmethod
    def malformed(cls, authenticator_id: str = "", description: str = "") -> AuthenticationOutcome:
        return cls(
            result=AuthResult.MALFORMED,
            authenticator_id=authenticator_id,
            error_description=description or "Credential is malformed",
        )

    @classmethod
    def invalid(cls, authenticator_id: str = "", description: str = "") -> AuthenticationOutcome:
        return cls(
            result=AuthResult.INVALID,
            authenticator_id=authenticator_id,
            error_description=description or "Credential verification failed",
        )

    @classmethod
    def expired(cls, authenticator_id: str = "", description: str = "") -> AuthenticationOutcome:
        return cls(
            result=AuthResult.EXPIRED,
            authenticator_id=authenticator_id,
            error_description=description or "Credential has expired",
        )

    @classmethod
    def revoked(cls, authenticator_id: str = "", description: str = "") -> AuthenticationOutcome:
        return cls(
            result=AuthResult.REVOKED,
            authenticator_id=authenticator_id,
            error_description=description or "Credential has been revoked",
        )

    @classmethod
    def internal_error(cls, authenticator_id: str = "", error: BaseException | None = None) -> AuthenticationOutcome:
        return cls(
            result=AuthResult.INTERNAL_ERROR,
            authenticator_id=authenticator_id,
            error_description="Authentication service error",
            internal_error=error,
        )

    @property
    def is_success(self) -> bool:
        return self.result.is_success

    @property
    def safe_description(self) -> str:
        """A description safe to include in WWW-Authenticate; never leaks internals."""
        if self.result is AuthResult.INTERNAL_ERROR:
            return "Authentication service error"
        return self.error_description
