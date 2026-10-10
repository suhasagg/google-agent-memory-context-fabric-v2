"""Config-driven identity validation. Principals never come from HTTP request bodies.

Authentication modes:
* development only: literal API keys
* production: PBKDF2-HMAC-SHA256 hashed keys or asymmetric OIDC JWTs

All options deliberately fail closed on malformed configuration. TLS, service-to-
service mTLS, IP throttling and token issuance belong to the deployment gateway.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from urllib.parse import urlparse
from functools import lru_cache

from .core import CLASSIFICATION, Principal


class AuthConfigError(RuntimeError):
    pass


class AuthenticationFailed(ValueError):
    pass


def hash_api_key(secret: str, iterations: int = 310_000, salt: bytes | None = None) -> str:
    """Return a salted PBKDF2 verifier, NOT a raw API key."""
    if len(secret) < 16 or not 100_000 <= iterations <= 2_000_000:
        raise ValueError("key must contain >=16 characters; iterations must be 100000..2000000")
    salt = salt if salt is not None else secrets.token_bytes(16)
    if len(salt) < 16:
        raise ValueError("salt too short")
    value = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${value.hex()}"


def verify_api_key(secret: str, verifier: str) -> bool:
    try:
        algorithm, rounds, salt_hex, result_hex = verifier.split("$")
        iterations = int(rounds)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(result_hex)
        if algorithm != "pbkdf2_sha256" or not 100_000 <= iterations <= 2_000_000:
            return False
        if len(salt) < 16 or len(expected) != 32 or len(secret) > 4096:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, AttributeError):
        return False


def _read_mapping(name: str) -> dict:
    raw = os.getenv(name)
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise AuthConfigError(f"{name} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise AuthConfigError(f"{name} must be a JSON object")
    return value


def _principal(mapping: dict) -> Principal:
    if not isinstance(mapping, dict):
        raise AuthConfigError("principal entry must be an object")
    allowed = {"tenant", "agent", "subject", "clearance", "roles"}
    if set(mapping) - allowed:
        raise AuthConfigError("unknown principal fields")
    roles = mapping.get("roles", ())
    if not isinstance(roles, (list, tuple)) or any(not isinstance(x, str) for x in roles):
        raise AuthConfigError("principal roles must be a list")
    try:
        return Principal(tenant=mapping["tenant"], agent=mapping["agent"],
                         subject=mapping.get("subject", "service-account"),
                         clearance=mapping.get("clearance", "INTERNAL"), roles=tuple(roles))
    except (ValueError, TypeError, KeyError) as exc:
        raise AuthConfigError("invalid configured principal") from exc


def validate_security_config() -> None:
    """Call at HTTP service startup; never silently enable developer credentials."""
    mode = os.getenv("FABRIC_MODE", "development")
    if mode not in ("development", "production"):
        raise AuthConfigError("FABRIC_MODE must be development or production")
    hashed = _read_mapping("FABRIC_HASHED_CREDENTIALS_JSON")
    plain = _read_mapping("FABRIC_CREDENTIALS_JSON")
    for item in hashed.values():
        if not isinstance(item, dict) or not verify_verifier_format(item.get("hash")):
            raise AuthConfigError("invalid hashed credential entry")
        _principal(item.get("principal", {}))
    for item in plain.values():
        _principal(item)
    oidc = os.getenv("FABRIC_OIDC_ISSUER")
    if oidc:
        issuer = urlparse(oidc)
        jwks = urlparse(os.getenv("FABRIC_OIDC_JWKS_URL", ""))
        if issuer.scheme != "https" or not issuer.netloc or jwks.scheme != "https" or not jwks.netloc:
            raise AuthConfigError("OIDC issuer and JWKS URL must be https")
        if not os.getenv("FABRIC_OIDC_AUDIENCE"):
            raise AuthConfigError("FABRIC_OIDC_AUDIENCE required")
    if mode == "production":
        if plain or os.getenv("FABRIC_API_KEY"):
            raise AuthConfigError("plaintext keys forbidden in production")
        if not hashed and not oidc:
            raise AuthConfigError("production requires OIDC or hashed credentials")
        if os.getenv("FABRIC_AUTO_CAPTURE") == "1":
            raise AuthConfigError("automatic capture not supported in production HTTP process")


def verify_verifier_format(verifier: object) -> bool:
    if not isinstance(verifier, str):
        return False
    bits = verifier.split("$")
    if len(bits) != 4 or bits[0] != "pbkdf2_sha256":
        return False
    try:
        return 100_000 <= int(bits[1]) <= 2_000_000 and len(bytes.fromhex(bits[2])) >= 16 and len(bytes.fromhex(bits[3])) == 32
    except ValueError:
        return False


@lru_cache(maxsize=8)
def _jwks_client(url: str):
    import jwt
    # Caches fetched JWKS for five minutes. Unknown key IDs trigger PyJWT refresh.
    return jwt.PyJWKClient(url, cache_jwk_set=True, lifespan=300)


def _verify_oidc(token: str) -> Principal:
    try:
        import jwt
    except ImportError as exc:
        raise AuthConfigError("install optional 'oidc' dependencies to enable OIDC") from exc
    url = os.environ["FABRIC_OIDC_JWKS_URL"]
    issuer = os.environ["FABRIC_OIDC_ISSUER"]
    audience = os.environ["FABRIC_OIDC_AUDIENCE"]
    # OIDC keys come ONLY from operator-configured JWKS, never from token headers.
    key = _jwks_client(url).get_signing_key_from_jwt(token)
    claims = jwt.decode(token, key.key, algorithms=["RS256", "ES256"], issuer=issuer,
                        audience=audience, options={"require": ["exp", "iat", "sub", "iss", "aud"]}, leeway=30)
    namespace = os.getenv("FABRIC_OIDC_CLAIMS_NAMESPACE", "fabric")
    attrs = claims.get(namespace, {})
    if not isinstance(attrs, dict):
        raise AuthenticationFailed("missing fabric identity claims")
    tenant, agent = attrs.get("tenant"), attrs.get("agent")
    # No self-provisioning: signed identities map to allow-listed namespaces.
    allow_tenants = {x.strip() for x in os.getenv("FABRIC_OIDC_ALLOWED_TENANTS", "").split(",") if x.strip()}
    if not allow_tenants or tenant not in allow_tenants:
        raise AuthenticationFailed("tenant not allowed by deployment")
    if not isinstance(agent, str) or not re.fullmatch(r"[A-Za-z0-9_.:@-]{1,128}", agent):
        raise AuthenticationFailed("invalid agent claim")
    requested_roles = attrs.get("roles", [])
    if not isinstance(requested_roles, list) or any(not isinstance(r, str) for r in requested_roles):
        raise AuthenticationFailed("invalid roles claim")
    allowed_roles = set(filter(None, os.getenv("FABRIC_OIDC_ALLOWED_ROLES", "").split(",")))
    roles = tuple(r for r in requested_roles if r in allowed_roles)
    requested_clearance = attrs.get("clearance", "INTERNAL")
    max_clearance = os.getenv("FABRIC_OIDC_MAX_CLEARANCE", "INTERNAL")
    if max_clearance not in CLASSIFICATION or requested_clearance not in CLASSIFICATION:
        raise AuthenticationFailed("invalid clearance")
    if CLASSIFICATION[requested_clearance] > CLASSIFICATION[max_clearance]:
        raise AuthenticationFailed("clearance exceeds deployment policy")
    return Principal(tenant=tenant, agent=agent, subject=claims["sub"],
                     clearance=requested_clearance, roles=roles)


def authenticate(*, api_key: str | None = None, bearer: str | None = None) -> Principal:
    if bool(api_key) == bool(bearer):
        raise AuthenticationFailed("provide exactly one credential")
    if bearer:
        if not os.getenv("FABRIC_OIDC_ISSUER"):
            raise AuthenticationFailed("OIDC not enabled")
        try:
            return _verify_oidc(bearer)
        except AuthConfigError:
            raise
        except Exception as exc:
            # Deliberately do not expose token verification errors to callers.
            raise AuthenticationFailed("invalid bearer token") from exc
    if not api_key or len(api_key) > 4096:
        raise AuthenticationFailed("invalid API key")
    for entry in _read_mapping("FABRIC_HASHED_CREDENTIALS_JSON").values():
        if verify_api_key(api_key, entry["hash"]):
            return _principal(entry["principal"])
    if os.getenv("FABRIC_MODE", "development") != "production":
        for secret, principal in _read_mapping("FABRIC_CREDENTIALS_JSON").items():
            if hmac.compare_digest(api_key, secret):
                return _principal(principal)
        dev_secret = os.getenv("FABRIC_API_KEY")
        if dev_secret and hmac.compare_digest(api_key, dev_secret):
            return Principal(tenant=os.getenv("FABRIC_TENANT", "local"), agent=os.getenv("FABRIC_AGENT", "api"),
                             subject=os.getenv("FABRIC_SUBJECT", "local-user"),
                             clearance=os.getenv("FABRIC_CLEARANCE", "INTERNAL"),
                             roles=tuple(filter(None, (x.strip() for x in os.getenv("FABRIC_ROLES", "").split(",")))))
    raise AuthenticationFailed("invalid API key")
