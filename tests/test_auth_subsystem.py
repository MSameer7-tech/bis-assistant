"""
Phase 14 - Supabase Authentication Subsystem Verification Tests.

Tests cover:
1. Public client configuration isolation (GET /api/auth/config):
   - Exposes supabase_url, supabase_anon_key, and supabase_publishable_key.
   - Strictly forbids leakage of SUPABASE_SERVICE_ROLE_KEY or SUPABASE_JWT_SECRET.
   - Prefers SUPABASE_PUBLISHABLE_KEY terminology.
2. Modern Asymmetric JWKS verification:
   - Verifies RS256/ES256 tokens using standard PyJWT + PyJWKClient mechanisms.
   - Validates temporal claims (exp, nbf).
   - Validates audience (aud == 'authenticated').
   - Validates subject claim (sub).
   - Rejects expired, tampered, or mismatched-signature asymmetric tokens.
3. Symmetric HS256 Compatibility Fallback:
   - Verifies HS256 when SUPABASE_JWT_SECRET is explicitly configured.
   - Rejects HS256 when SUPABASE_JWT_SECRET is not configured (non-mandatory secret).
   - Rejects signature mismatches.
4. FastAPI Endpoints & Security Dependencies:
   - GET /api/auth/config
   - GET /auth/callback
   - GET /api/v1/auth/me (Protected - 401 unauthenticated, 200 authenticated)
   - POST /api/v1/query (Guest Access 100% preserved, identity attached when token present)
5. Unified Production Server Routing Check.
"""

import os
import time
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import HTTPException
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from backend.auth import (
    get_supabase_public_config,
    verify_supabase_jwt,
    get_current_user_optional,
    get_current_user_required,
    get_jwks_client,
)
from backend.app import app


# -----------------------------------------------------------------------------
# Test Cryptographic Key Generation (RSA for RS256 tests)
# -----------------------------------------------------------------------------
_TEST_RSA_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_TEST_RSA_PUB = _TEST_RSA_KEY.public_key()
_TEST_HS256_SECRET = "bis-test-jwt-secret-key-32-chars-long!"


def create_test_rs256_jwt(
    payload: dict,
    private_key=_TEST_RSA_KEY,
    headers: dict = None
) -> str:
    """Helper to generate an RS256 signed JWT for asymmetric test suites."""
    h = {"alg": "RS256", "typ": "JWT", "kid": "test-key-id-1"}
    if headers:
        h.update(headers)
    return jwt.encode(payload, private_key, algorithm="RS256", headers=h)


def create_test_hs256_jwt(
    payload: dict,
    secret: str = _TEST_HS256_SECRET
) -> str:
    """Helper to generate an HS256 signed JWT for legacy fallback test suites."""
    return jwt.encode(payload, secret, algorithm="HS256")


# -----------------------------------------------------------------------------
# 1. Configuration & Credential Safety
# -----------------------------------------------------------------------------
def test_public_config_isolation(monkeypatch):
    """Verify that get_supabase_public_config only returns public fields and zero secrets."""
    monkeypatch.setenv("SUPABASE_URL", "https://testproject.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test_token_123")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "SUPER_SECRET_SERVICE_ROLE_DO_NOT_EXPOSE")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "SECRET_JWT_SIGNING_KEY")

    cfg = get_supabase_public_config()
    assert cfg["supabase_url"] == "https://testproject.supabase.co"
    assert cfg["supabase_publishable_key"] == "sb_publishable_test_token_123"
    assert cfg["supabase_anon_key"] == "sb_publishable_test_token_123"

    # Strict negative check: secrets must NEVER be present
    assert "supabase_service_role_key" not in cfg
    assert "service_role_key" not in cfg
    assert "SUPABASE_SERVICE_ROLE_KEY" not in cfg
    assert "supabase_jwt_secret" not in cfg
    assert "jwt_secret" not in cfg
    assert "SUPER_SECRET_SERVICE_ROLE_DO_NOT_EXPOSE" not in str(cfg)
    assert "SECRET_JWT_SIGNING_KEY" not in str(cfg)


def test_api_auth_config_endpoint(monkeypatch):
    """Test GET /api/auth/config via FastAPI TestClient."""
    monkeypatch.setenv("SUPABASE_URL", "https://testproject.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_abc_456")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "SECRET_KEY_NEVER_LEAK")

    client = TestClient(app)
    response = client.get("/api/auth/config")
    assert response.status_code == 200
    data = response.json()
    assert data["supabase_url"] == "https://testproject.supabase.co"
    assert data["supabase_publishable_key"] == "sb_publishable_abc_456"
    assert data["supabase_anon_key"] == "sb_publishable_abc_456"
    assert "SECRET_KEY_NEVER_LEAK" not in response.text


# -----------------------------------------------------------------------------
# 2. Modern Asymmetric JWKS Verification
# -----------------------------------------------------------------------------
def test_verify_asymmetric_jwt_valid():
    """Verify that a properly signed RS256 token passes and extracts user claims."""
    payload = {
        "sub": "00000000-0000-0000-0000-000000000001",
        "email": "scientist@bis.gov.in",
        "role": "authenticated",
        "aud": "authenticated",
        "exp": time.time() + 3600
    }
    token = create_test_rs256_jwt(payload)
    user = verify_supabase_jwt(token, public_key=_TEST_RSA_PUB)
    assert user["user_id"] == "00000000-0000-0000-0000-000000000001"
    assert user["email"] == "scientist@bis.gov.in"
    assert user["role"] == "authenticated"


def test_verify_asymmetric_jwt_via_mock_jwk_client():
    """Verify asymmetric token resolution using PyJWKClient interface."""
    payload = {
        "sub": "user-jwks-789",
        "email": "auditor@bis.gov.in",
        "aud": "authenticated",
        "exp": time.time() + 3600
    }
    token = create_test_rs256_jwt(payload)

    # Mock PyJWKClient that resolves to the test public key
    mock_jwk_client = MagicMock()
    mock_signing_key = MagicMock()
    mock_signing_key.key = _TEST_RSA_PUB
    mock_jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key

    user = verify_supabase_jwt(token, jwk_client=mock_jwk_client)
    assert user["user_id"] == "user-jwks-789"
    assert user["email"] == "auditor@bis.gov.in"


def test_verify_asymmetric_jwt_expired():
    """Verify that expired asymmetric tokens raise HTTP 401."""
    expired_payload = {
        "sub": "user-expired-123",
        "email": "user@example.com",
        "aud": "authenticated",
        "exp": time.time() - 3600  # Expired 1 hour ago
    }
    token = create_test_rs256_jwt(expired_payload)
    with pytest.raises(HTTPException) as exc:
        verify_supabase_jwt(token, public_key=_TEST_RSA_PUB)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail.lower()


def test_verify_asymmetric_jwt_missing_sub():
    """Verify that asymmetric tokens missing 'sub' claim raise HTTP 401."""
    payload = {
        "email": "user@example.com",
        "aud": "authenticated",
        "exp": time.time() + 3600
    }
    token = create_test_rs256_jwt(payload)
    with pytest.raises(HTTPException) as exc:
        verify_supabase_jwt(token, public_key=_TEST_RSA_PUB)
    assert exc.value.status_code == 401
    assert "sub" in exc.value.detail.lower()


def test_verify_asymmetric_jwt_invalid_aud():
    """Verify that asymmetric tokens with invalid audience raise HTTP 401."""
    payload = {
        "sub": "user-123",
        "aud": "wrong-audience",
        "exp": time.time() + 3600
    }
    token = create_test_rs256_jwt(payload)
    with pytest.raises(HTTPException) as exc:
        verify_supabase_jwt(token, public_key=_TEST_RSA_PUB)
    assert exc.value.status_code == 401
    assert "audience" in exc.value.detail.lower()


def test_verify_asymmetric_jwt_signature_mismatch():
    """Verify that RS256 token signed by an untrusted key raises HTTP 401."""
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    payload = {
        "sub": "user-123",
        "email": "user@example.com",
        "aud": "authenticated",
        "exp": time.time() + 3600
    }
    token = create_test_rs256_jwt(payload, private_key=other_key)
    with pytest.raises(HTTPException) as exc:
        verify_supabase_jwt(token, public_key=_TEST_RSA_PUB)
    assert exc.value.status_code == 401
    assert "signature" in exc.value.detail.lower()


# -----------------------------------------------------------------------------
# 3. Symmetric HS256 Compatibility Fallback
# -----------------------------------------------------------------------------
def test_verify_hs256_with_secret_configured(monkeypatch):
    """Verify HS256 fallback works when SUPABASE_JWT_SECRET is explicitly provided."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", _TEST_HS256_SECRET)
    payload = {
        "sub": "legacy-user-456",
        "email": "legacy@bis.gov.in",
        "aud": "authenticated",
        "exp": time.time() + 3600
    }
    token = create_test_hs256_jwt(payload)
    user = verify_supabase_jwt(token)
    assert user["user_id"] == "legacy-user-456"
    assert user["email"] == "legacy@bis.gov.in"


def test_verify_hs256_rejected_when_secret_absent(monkeypatch):
    """
    Verify that HS256 is rejected if SUPABASE_JWT_SECRET is not configured.
    Guarantees that SUPABASE_JWT_SECRET is not mandatory for asymmetric projects.
    """
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    payload = {
        "sub": "legacy-user-456",
        "email": "legacy@bis.gov.in",
        "aud": "authenticated",
        "exp": time.time() + 3600
    }
    token = create_test_hs256_jwt(payload)
    with pytest.raises(HTTPException) as exc:
        verify_supabase_jwt(token)
    assert exc.value.status_code == 401
    assert "supabase_jwt_secret" in exc.value.detail.lower()


def test_verify_hs256_signature_mismatch(monkeypatch):
    """Verify HS256 signature mismatch raises HTTP 401."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", _TEST_HS256_SECRET)
    payload = {
        "sub": "legacy-user-456",
        "aud": "authenticated",
        "exp": time.time() + 3600
    }
    # Signed with wrong secret
    token = create_test_hs256_jwt(payload, secret="wrong-secret-signature-32-chars-long!")
    with pytest.raises(HTTPException) as exc:
        verify_supabase_jwt(token)
    assert exc.value.status_code == 401
    assert "signature" in exc.value.detail.lower()


# -----------------------------------------------------------------------------
# 4. Protected Endpoint (/api/v1/auth/me)
# -----------------------------------------------------------------------------
def test_auth_me_without_token():
    """GET /api/v1/auth/me must return 401/403 when no token is provided."""
    client = TestClient(app)
    response = client.get("/api/v1/auth/me")
    assert response.status_code in (401, 403)


def test_auth_me_with_valid_token(monkeypatch):
    """GET /api/v1/auth/me returns user profile when valid token provided."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", _TEST_HS256_SECRET)
    payload = {
        "sub": "valid-user-id-777",
        "email": "analyst@bis.gov.in",
        "aud": "authenticated",
        "exp": time.time() + 3600
    }
    token = create_test_hs256_jwt(payload)
    client = TestClient(app)
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert data["user_id"] == "valid-user-id-777"
    assert data["email"] == "analyst@bis.gov.in"


# -----------------------------------------------------------------------------
# 5. Guest Access Invariant (CRITICAL)
# -----------------------------------------------------------------------------
def test_guest_query_unaffected_post_api_v1_query():
    """
    CRITICAL INVARIANT: Existing BIS RAG queries without Authorization header
    MUST proceed normally and not be blocked or rejected by auth.
    """
    client = TestClient(app)
    mock_answer = type("MockAnswer", (), {
        "model_dump": lambda self: {
            "status": "VERIFIED",
            "query": "cement standards",
            "answer_markdown": "IS 269:2015 applies to Ordinary Portland Cement."
        }
    })()

    mock_engine = MagicMock()
    mock_engine.process_query.return_value = mock_answer

    with patch("backend.app.get_intelligence_engine", return_value=mock_engine):
        response = client.post(
            "/api/v1/query",
            json={"query": "cement standards", "top_k": 3}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "cement standards"
        assert "IS 269" in data["answer_markdown"]
        # Guest queries do not have authenticated_user attached
        assert "authenticated_user" not in data


def test_authenticated_query_attaches_identity(monkeypatch):
    """
    When a valid token is sent with /api/v1/query, the response completes
    and includes the verified authenticated_user object.
    """
    monkeypatch.setenv("SUPABASE_JWT_SECRET", _TEST_HS256_SECRET)
    payload = {
        "sub": "user-scientist-888",
        "email": "scientist@bis.gov.in",
        "aud": "authenticated",
        "exp": time.time() + 3600
    }
    token = create_test_hs256_jwt(payload)
    client = TestClient(app)

    mock_answer = type("MockAnswer", (), {
        "model_dump": lambda self: {
            "status": "VERIFIED",
            "query": "packaged drinking water",
            "answer_markdown": "IS 14543 applies to packaged drinking water."
        }
    })()

    mock_engine = MagicMock()
    mock_engine.process_query.return_value = mock_answer

    with patch("backend.app.get_intelligence_engine", return_value=mock_engine):
        response = client.post(
            "/api/v1/query",
            json={"query": "packaged drinking water", "top_k": 3},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "authenticated_user" in data
        assert data["authenticated_user"]["user_id"] == "user-scientist-888"
        assert data["authenticated_user"]["email"] == "scientist@bis.gov.in"


# -----------------------------------------------------------------------------
# 6. Auth Callback & Login Route Handlers
# -----------------------------------------------------------------------------
def test_auth_callback_route_fastapi():
    """GET /auth/callback serves the auth-callback.html document."""
    client = TestClient(app)
    response = client.get("/auth/callback")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Authenticating" in response.text or "callback" in response.text.lower()


def test_login_page_routes_fastapi():
    """GET /login and /signin serve the login.html document."""
    client = TestClient(app)
    for path in ["/login", "/signin", "/auth/login"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "Sign in to BIS Assistant" in response.text
        assert "Continue with Google" in response.text
        assert "Continue with GitHub" in response.text
        assert "Continue as Guest" in response.text


# -----------------------------------------------------------------------------
# 7. Unified Production Server Routing Check
# -----------------------------------------------------------------------------
def test_unified_server_callback_handler():
    """Verify that scripts/phase12_e_production_rag.py handler recognizes /auth/callback and /login."""
    from scripts.phase12_e_production_rag import ProductionHTTPHandler
    import inspect
    source = inspect.getsource(ProductionHTTPHandler.do_GET)
    assert "/api/auth/config" in source
    assert "/auth/callback" in source
    assert "/login" in source
