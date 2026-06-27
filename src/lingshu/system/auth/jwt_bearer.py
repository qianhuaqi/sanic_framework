from __future__ import annotations

import time
from typing import Any

import jwt
from jwt import PyJWTError

from lingshu.system.auth.principal import Principal
from lingshu.system.auth.result import AuthenticationOutcome, AuthResult


_DEFAULT_LEEWAY = 0.0


class JwtBearerAuthenticator:
    """Official Bearer/JWT reference authenticator.

    Security properties:
    - Strictly parses ``Authorization: Bearer <token>``.
    - Rejects ``alg=none`` unconditionally via explicit algorithm allowlist.
    - Never implements its own signing or verification crypto — delegates to
      the PyJWT library which uses the ``cryptography`` package internally.
    - Internal exceptions (including library errors) are never leaked to the
      client; only a safe description is exposed.
    - Configurable ``leeway`` for minor clock skew.
    - Configurable ``issuer`` and ``audience`` verification.

    Configuration is provided at construction time; it must NOT come from
    request-time input.
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
        alg_set = set(algorithms)
        if "none" in alg_set:
            raise ValueError("alg=none is prohibited")
        # Only allow algorithms PyJWT supports for HMAC/RS/ES verification.
        permitted = {
            "HS256", "HS384", "HS512",
            "RS256", "RS384", "RS512",
            "ES256", "ES384", "ES512",
            "PS256", "PS384", "PS512",
            "EdDSA",
        }
        unsupported = alg_set - permitted
        if unsupported:
            raise ValueError(f"Unsupported algorithm(s): {', '.join(sorted(unsupported))}")

        self._secret = secret
        self._algorithms = tuple(alg_set & permitted)
        self._issuer = issuer
        self._audience = audience
        self._leeway = float(leeway)
        self._require_exp = bool(require_exp)
        self._subject_claim = subject_claim
        self._scopes_claim = scopes_claim

    async def authenticate(self, request) -> AuthenticationOutcome:
        auth_header = request.headers.get("Authorization")

        # --- MISSING: no header at all ---
        if not auth_header:
            return AuthenticationOutcome.missing(self.authenticator_id)

        # --- MALFORMED: header does not match Bearer scheme ---
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

        # --- Attempt decode + verify ---
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
            # alg=none or unsupported algorithm used in the token header
            return AuthenticationOutcome.invalid(self.authenticator_id, "Token algorithm is not allowed")
        except jwt.DecodeError as exc:
            # Includes InvalidSignatureError, InvalidTokenError subclasses
            exc_name = type(exc).__name__
            if "Signature" in exc_name:
                return AuthenticationOutcome.invalid(self.authenticator_id, "Token signature verification failed")
            return AuthenticationOutcome.malformed(self.authenticator_id, "Token could not be decoded")
        except PyJWTError:
            return AuthenticationOutcome.invalid(self.authenticator_id, "Token verification failed")
        except Exception as exc:
            return AuthenticationOutcome.internal_error(self.authenticator_id, error=exc)

        # --- Extract subject ---
        subject = payload.get(self._subject_claim)
        if not subject or not isinstance(subject, str):
            return AuthenticationOutcome.malformed(
                self.authenticator_id,
                "Token is missing a valid subject claim",
            )

        # --- Build scopes ---
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

        # --- Build claims (only verified payload) ---
        # We copy the verified claims into a frozen mapping.  The caller
        # should not mutate these.
        verified_claims: dict[str, Any] = dict(payload)

        principal = Principal.create(
            subject=subject,
            authenticator_id=self.authenticator_id,
            scopes=scopes,
            claims=verified_claims,
        )
        return AuthenticationOutcome.success(principal)

    # -- Utility for tests: encode a valid token --

    def encode_token(
        self,
        *,
        subject: str,
        scopes: list[str] | tuple[str, ...] | None = None,
        expire_in: int = 3600,
        algorithm: str | None = None,
        extra_claims: dict[str, Any] | None = None,
        issuer: str | None = ...,
        audience: str | None = ...,
    ) -> str:
        """Encode a valid JWT for testing purposes.

        Uses the authenticator's own secret and algorithm.  This method exists
        so that tests can generate tokens without importing jwt directly or
        knowing the secret.
        """
        alg = algorithm or self._algorithms[0]
        if alg not in self._algorithms:
            raise ValueError(f"Algorithm {alg!r} is not in the configured allowlist")
        payload: dict[str, Any] = {
            self._subject_claim: str(subject),
            "exp": int(time.time()) + int(expire_in),
        }
        if scopes is not None:
            payload[self._scopes_claim] = list(scopes) if self._scopes_claim else None
        if extra_claims:
            payload.update(extra_claims)
        if issuer is ...:
            issuer = self._issuer
        if issuer:
            payload["iss"] = issuer
        if audience is ...:
            audience = self._audience if isinstance(self._audience, str) else None
        if audience:
            payload["aud"] = audience
        return jwt.encode(payload, self._secret, algorithm=alg)

    def encode_expired_token(
        self,
        *,
        subject: str,
        algorithm: str | None = None,
    ) -> str:
        """Encode a token that is already expired."""
        alg = algorithm or self._algorithms[0]
        payload: dict[str, Any] = {
            self._subject_claim: str(subject),
            "exp": int(time.time()) - 3600,
        }
        if self._issuer:
            payload["iss"] = self._issuer
        if isinstance(self._audience, str):
            payload["aud"] = self._audience
        return jwt.encode(payload, self._secret, algorithm=alg)
