"""
Backend Authentication & Supabase JWT Verification Module for BIS-AI-Assistant (Phase 14).

Provides:
- Asymmetric JWKS signature verification for modern Supabase JWTs (RS256, ES256, EdDSA)
  using the project JWKS endpoint: https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json
- Industry-standard PyJWT + PyJWKClient key caching and verification (no manual crypto).
- Legacy/shared-secret HS256 fallback when SUPABASE_JWT_SECRET is explicitly configured.
- FastAPI dependencies:
    - get_current_user_optional: Preserves 100% guest access on existing endpoints.
    - get_current_user_required: Enforces authentication on user-specific endpoints.
- Safe public configuration accessor exposing publishable key without private secrets.
"""

import os
import sys
import logging
from typing import Optional, Dict, Any
from pathlib import Path

import jwt
from jwt import PyJWKClient
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidTokenError,
    PyJWTError,
    PyJWKClientError,
)
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger("bis_auth")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass


# Supported asymmetric signing algorithms from Supabase
ASYMMETRIC_ALGORITHMS = [
    "RS256", "RS384", "RS512",
    "ES256", "ES384", "ES512",
    "EdDSA"
]

# Cache of PyJWKClient instances keyed by JWKS URL
_jwks_clients: Dict[str, PyJWKClient] = {}


def get_jwks_client(supabase_url: str) -> PyJWKClient:
    """
    Returns or initializes a cached PyJWKClient for the given Supabase URL.
    Fetches public keys from: https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json
    Keys are cached in memory to minimize network overhead and latency.
    """
    cleaned_url = supabase_url.strip().rstrip("/")
    jwks_url = f"{cleaned_url}/auth/v1/.well-known/jwks.json"
    if jwks_url not in _jwks_clients:
        _jwks_clients[jwks_url] = PyJWKClient(
            jwks_url,
            cache_keys=True,
            max_cached_keys=16,
            cache_jwk_set=True,
            lifespan=3600
        )
    return _jwks_clients[jwks_url]


def get_supabase_public_config() -> Dict[str, str]:
    """
    Returns only the non-sensitive public Supabase client configuration.
    Prefers the current publishable client-key terminology (SUPABASE_PUBLISHABLE_KEY)
    while maintaining full backwards compatibility with SUPABASE_ANON_KEY.

    CRITICAL SECURITY GUARANTEE:
    Never exposes service-role keys, database passwords, or JWT secrets.
    """
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    publishable_key = (
        os.getenv("SUPABASE_PUBLISHABLE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
        or ""
    ).strip()
    return {
        "supabase_url": url,
        "supabase_anon_key": publishable_key,
        "supabase_publishable_key": publishable_key
    }


def verify_supabase_jwt(
    token: str,
    jwk_client: Optional[PyJWKClient] = None,
    public_key: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Validates a Supabase JWT token using standard, high-quality JWT libraries:
    1. Unverified header check to identify algorithm ('alg') and key ID ('kid').
    2. Asymmetric verification (RS256, ES256, etc.) using Supabase JWKS endpoint.
    3. HS256 compatibility fallback ONLY if SUPABASE_JWT_SECRET is explicitly configured.
    4. Comprehensive claim validation:
       - 'exp' (expiration)
       - 'nbf' (not before)
       - 'aud' must match 'authenticated'
       - 'iss' must match '<supabase_url>/auth/v1' (if SUPABASE_URL configured)
       - 'sub' (user ID) presence and validity
    5. Returns verified claims dict:
       {"user_id": str, "email": Optional[str], "role": str, "claims": dict}

    Raises HTTPException(401) on any validation or key retrieval failure.
    """
    if not token or not isinstance(token, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or empty authentication token."
        )

    # 1. Inspect unverified header for algorithm and kid
    try:
        unverified_header = jwt.get_unverified_header(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Malformed authentication token: {e}"
        )

    alg = unverified_header.get("alg", "").upper()
    if not alg:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing algorithm ('alg') in header."
        )

    supabase_url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    expected_issuer = f"{supabase_url}/auth/v1" if supabase_url else None

    # Inspect unverified claims to validate issuer if present
    try:
        unverified_claims = jwt.decode(token, options={"verify_signature": False})
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Malformed authentication token: {e}"
        )

    if expected_issuer and "iss" in unverified_claims:
        iss = str(unverified_claims["iss"]).rstrip("/")
        if iss != expected_issuer.rstrip("/") and supabase_url not in iss:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: issuer ('iss') mismatch."
            )

    decode_options = {
        "require": ["exp", "sub"],
        "verify_signature": True,
        "verify_exp": True,
        "verify_aud": True
    }

    # 2. Asymmetric Verification (RS256, ES256, EdDSA, etc.) via Supabase JWKS
    if alg in ASYMMETRIC_ALGORITHMS:
        key_to_use = public_key

        if key_to_use is None:
            active_client = jwk_client
            if active_client is None:
                if not supabase_url:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Asymmetric token verification requires SUPABASE_URL to be configured."
                    )
                active_client = get_jwks_client(supabase_url)

            try:
                signing_key = active_client.get_signing_key_from_jwt(token)
                key_to_use = signing_key.key
            except PyJWKClientError as err:
                logger.warning("JWKS key resolution failed: %s", err)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Unable to find signing key in Supabase JWKS: {err}"
                )
            except Exception as err:
                logger.warning("JWKS network or parsing error: %s", err)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Failed to fetch or parse Supabase JWKS: {err}"
                )

        try:
            payload = jwt.decode(
                token,
                key_to_use,
                algorithms=ASYMMETRIC_ALGORITHMS,
                audience="authenticated",
                options=decode_options
            )
        except ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token has expired."
            )
        except InvalidAudienceError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: audience ('aud') must be 'authenticated'."
            )
        except InvalidSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token signature verification failed."
            )
        except (InvalidTokenError, PyJWTError) as err:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {err}"
            )

    # 3. Symmetric HS256 Fallback (for legacy / shared-secret projects only)
    elif alg == "HS256":
        jwt_secret = (os.getenv("SUPABASE_JWT_SECRET") or "").strip()
        if not jwt_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="HS256 tokens require SUPABASE_JWT_SECRET to be configured on the server."
            )

        try:
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                options=decode_options
            )
        except ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token has expired."
            )
        except InvalidAudienceError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: audience ('aud') must be 'authenticated'."
            )
        except InvalidIssuerError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: issuer ('iss') mismatch."
            )
        except InvalidSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token signature verification failed."
            )
        except (InvalidTokenError, PyJWTError) as err:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {err}"
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unsupported token signing algorithm: '{alg}'."
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject claim ('sub')."
        )

    return {
        "user_id": str(user_id),
        "email": payload.get("email"),
        "role": payload.get("role", "authenticated"),
        "claims": payload
    }


# -----------------------------------------------------------------------------
# FastAPI Security Dependencies
# -----------------------------------------------------------------------------
# auto_error=False ensures missing Authorization header returns None rather than HTTP 403/401
_optional_bearer = HTTPBearer(auto_error=False)
_required_bearer = HTTPBearer(auto_error=True)


async def get_current_user_optional(
    auth_creds: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer)
) -> Optional[Dict[str, Any]]:
    """
    FastAPI dependency for endpoints with OPTIONAL authentication (e.g. BIS RAG query).
    - If Authorization header is absent -> Returns None (continues as Guest).
    - If Authorization header is valid -> Returns verified user dictionary.
    - If Authorization header is malformed/invalid -> Raises HTTP 401.
    Preserves 100% guest access while preventing spoofed/tampered tokens.
    """
    if not auth_creds:
        return None

    token = auth_creds.credentials
    return verify_supabase_jwt(token)


async def get_current_user_required(
    auth_creds: HTTPAuthorizationCredentials = Depends(_required_bearer)
) -> Dict[str, Any]:
    """
    FastAPI dependency for endpoints that REQUIRE authentication (e.g. GET /api/v1/auth/me).
    - If Authorization header is absent -> FastAPI raises 401/403.
    - If Authorization header is invalid -> Raises 401.
    - Returns verified user dictionary with user_id, email, role.
    """
    token = auth_creds.credentials
    return verify_supabase_jwt(token)
