"""Test-only helpers for generating JWT tokens.

These utilities exist so that tests can create valid/expired tokens without
exposing signing capability on the production authenticator.
"""

from __future__ import annotations

import time
from typing import Any

import jwt


def encode_jwt_token(
    secret: str | bytes,
    algorithm: str,
    *,
    subject: str,
    scopes: list[str] | tuple[str, ...] | None = None,
    expire_in: int = 3600,
    extra_claims: dict[str, Any] | None = None,
    issuer: str | None = None,
    audience: str | None = None,
    subject_claim: str = "sub",
    scopes_claim: str | None = "scopes",
) -> str:
    payload: dict[str, Any] = {
        subject_claim: str(subject),
        "exp": int(time.time()) + int(expire_in),
    }
    if scopes is not None and scopes_claim:
        payload[scopes_claim] = list(scopes)
    if extra_claims:
        payload.update(extra_claims)
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience
    return jwt.encode(payload, secret, algorithm=algorithm)


def encode_expired_jwt_token(
    secret: str | bytes,
    algorithm: str,
    *,
    subject: str,
    issuer: str | None = None,
    audience: str | None = None,
    subject_claim: str = "sub",
) -> str:
    payload: dict[str, Any] = {
        subject_claim: str(subject),
        "exp": int(time.time()) - 3600,
    }
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience
    return jwt.encode(payload, secret, algorithm=algorithm)
