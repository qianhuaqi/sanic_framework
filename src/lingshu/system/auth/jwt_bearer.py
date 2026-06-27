from __future__ import annotations

from typing import Any

import jwt
from jwt import PyJWTError

from lingshu.system.auth.principal import Principal
from lingshu.system.auth.result import AuthenticationOutcome, AuthResult


_DEFAULT_LEEWAY = 0.0

_HMAC_ALGS = frozenset({"HS256", "HS384", "HS512"})
_ASYMMETRIC_ALGS = frozenset({
    "RS256", "RS384", "RS512",
    "ES256", "ES384", "ES512",
    "PS256", "PS384", "PS512",
    "EdDSA",
})
_PERMITTED_ALGS = _HMAC_ALGS | _ASYMMETRIC_ALGS


class JwtBearerAuthenticator:
    """Official Bearer/JWT reference authenticator.

    Security properties:
    - Strictly parses ``Authorization: Bearer <token>``.
    - Rejects ``alg=none`` unconditionally via explicit algorithm allowlist.
    - Never implements its own signing or verification crypto.
    - Preserves configured algorithm order; rejects duplicates.
    - Prohibits mixing HMAC and asymmetric algorithm families in one instance.
    - Internal exceptions are never leaked to the client.
    """

    authenticator_id = "jwt-bearer"

    def __init__(
        self,
        *,
        secret: str | bytes,
        algorithms: tuple[str, ...] | list[str],
        issuer: str | None = None,
        audience: str | list[str] | None = None,
        leeway: float = _DEFAULT_LEEWAY,
        require_exp: bool = True,
        subject_claim: str = "sub",
        scopes_claim: str | None = "scopes",
    ):
        if not secret:
            raise ValueError("JwtBearerAuthenticator requires a non-empty secret")
        if not algorithms:
            raise ValueError("JwtBearerAuthenticator requires at least one algorithm")

        # Preserve order, reject duplicates.
        seen: set[str] = set()
        ordered: list[str] = []
        for alg in algorithms:
            if alg in seen:
                raise ValueError(f"Duplicate algorithm: {alg}")
            seen.add(alg)
            ordered.append(alg)

        alg_set = set(ordered)
        if "none" in alg_set:
            raise ValueError("alg=none is prohibited")

        unsupported = alg_set - _PERMITTED_ALGS
        if unsupported:
            raise ValueError(f"Unsupported algorithm(s): {', '.join(sorted(unsupported))}")

        # Prohibit mixing HMAC and asymmetric families.
        is_hmac = bool(alg_set & _HMAC_ALGS)
        is_asymmetric = bool(alg_set & _ASYMMETRIC_ALGS)
        if is_hmac and is_asymmetric:
            raise ValueError(
                "Cannot mix HMAC and asymmetric algorithm families in one authenticator"
            )

        self._secret = secret
        self._algorithms = tuple(ordered)
        self._issuer = issuer
        self._audience = audience
        self._leeway = float(leeway)
        self._require_exp = bool(require_exp)
        self._subject_claim = subject_claim
        self._scopes_claim = scopes_claim

    @property
    def algorithms(self) -> tuple[str, ...]:
        return self._algorithms

    async def authenticate(self, request) -> AuthenticationOutcome:
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return AuthenticationOutcome.missing(self.authenticator_id)

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return AuthenticationOutcome.malformed(
                self.authenticator_id,
                "Authorization header must use Bearer scheme",
            )

        token = parts[1]
        if not token or token.count(".") != 2:
            return AuthenticationOutcome.malformed(
                self.authenticator_id,
                "Bearer token is not a well-formed JWT",
            )

        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self._secret,
                algorithms=list(self._algorithms),
                issuer=self._issuer,
                audience=self._audience,
                leeway=self._leeway,
                options={
                    "require": ["exp"] if self._require_exp else [],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": self._audience is not None,
                    "verify_iss": self._issuer is not None,
                },
            )
        except jwt.ExpiredSignatureError:
            return AuthenticationOutcome.expired(self.authenticator_id, "Token has expired")
        except jwt.InvalidAlgorithmError:
            return AuthenticationOutcome.invalid(self.authenticator_id, "Token algorithm is not allowed")
        except jwt.DecodeError as exc:
            exc_name = type(exc).__name__
            if "Signature" in exc_name:
                return AuthenticationOutcome.invalid(self.authenticator_id, "Token signature verification failed")
            return AuthenticationOutcome.malformed(self.authenticator_id, "Token could not be decoded")
        except PyJWTError:
            return AuthenticationOutcome.invalid(self.authenticator_id, "Token verification failed")
        except Exception as exc:
            return AuthenticationOutcome.internal_error(self.authenticator_id, error=exc)

        subject = payload.get(self._subject_claim)
        if not subject or not isinstance(subject, str):
            return AuthenticationOutcome.malformed(
                self.authenticator_id,
                "Token is missing a valid subject claim",
            )

        scopes: frozenset[str] = frozenset()
        if self._scopes_claim:
            raw_scopes = payload.get(self._scopes_claim)
            if raw_scopes is not None:
                if isinstance(raw_scopes, str):
                    scopes = frozenset(s.strip() for s in raw_scopes.split() if s.strip())
                elif isinstance(raw_scopes, (list, tuple, set)):
                    scopes = frozenset(str(s) for s in raw_scopes)
                else:
                    return AuthenticationOutcome.malformed(
                        self.authenticator_id,
                        "Token scopes claim is not a string or list",
                    )

        verified_claims: dict[str, Any] = dict(payload)

        principal = Principal.create(
            subject=subject,
            authenticator_id=self.authenticator_id,
            scopes=scopes,
            claims=verified_claims,
        )
        return AuthenticationOutcome.success(principal)
