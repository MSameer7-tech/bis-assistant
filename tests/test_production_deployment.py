"""
Production Deployment Pre-Flight Verification Suite.
Validates the decoupled deployment architecture:
  Frontend -> Vercel (static HTML/CSS/ES-modules)
  Backend  -> Railway (FastAPI on 0.0.0.0:$PORT)
"""

import os
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def client():
    from backend.app import app
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoints(client):
    """Verify production health endpoints on FastAPI."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["version"] == "13.0.0"
    assert data["engine"] == "Phase13GroundedRAGEngine"
    assert data["corpus_version"] == "v13.0"
    assert data["ps_coverage"] == "100.00%"
    assert data["release_gate"] == "PASSED"

    # Also verify /api/assistant/health
    res2 = client.get("/api/assistant/health")
    assert res2.status_code == 200
    assert res2.json()["status"] == "healthy"


def test_auth_config_endpoint(client):
    """Verify /api/auth/config returns safe public client config."""
    res = client.get("/api/auth/config")
    assert res.status_code == 200
    data = res.json()
    assert "supabase_url" in data
    assert "supabase_anon_key" in data
    # Ensure sensitive credentials are never leaked
    assert "service_role" not in str(data).lower()
    assert "jwt_secret" not in str(data).lower()


def test_assistant_query_endpoint(client):
    """Verify POST /api/assistant/query with Phase 13 v13.0 retrieval."""
    payload = {"query": "What is IS 8978?"}
    res = client.post("/api/assistant/query", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["SUFFICIENT", "PARTIAL"]
    assert "IS 8978" in data["answer"]
    evidence = data.get("rag", {}).get("evidence", []) or data.get("evidence", [])
    assert len(evidence) > 0
    assert data["provenance"]["rag_executed_first"] is True


def test_assistant_query_hindi(client):
    """Verify POST /api/assistant/query handles Hindi target language."""
    payload = {"query": "IS 8978 क्या है?", "target_language": "hi"}
    res = client.post("/api/assistant/query", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["SUFFICIENT", "PARTIAL"]
    assert data.get("language_detection", {}).get("response_language") == "hi"


def test_lab_finder_post_search(client):
    """Verify POST /api/labs/search returns qualified labs."""
    payload = {"standard": "IS 4985"}
    res = client.post("/api/labs/search", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["standard"] == "IS 4985"
    assert data["total_matching"] > 0
    assert len(data["candidates"]) > 0


def test_lab_finder_get_search(client):
    """Verify GET /api/labs/search?standard=IS%204985 returns qualified labs."""
    res = client.get("/api/labs/search?standard=IS%204985")
    assert res.status_code == 200
    data = res.json()
    assert data["standard"] == "IS 4985"
    assert data["total_matching"] > 0


def test_cors_middleware_headers(client):
    """Verify CORS preflight / Origin handling."""
    res = client.options(
        "/api/assistant/query",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
    )
    assert res.status_code == 200
    assert "access-control-allow-origin" in res.headers


def test_deployment_manifests_exist():
    """Verify all deployment configuration manifests exist and are valid."""
    procfile = ROOT_DIR / "Procfile"
    assert procfile.exists(), "Procfile must exist for Railway"
    content = procfile.read_text(encoding="utf-8")
    assert "uvicorn backend.app:app" in content
    assert "0.0.0.0" in content
    assert "PORT" in content

    railway_json = ROOT_DIR / "railway.json"
    assert railway_json.exists(), "railway.json must exist"
    railway_data = json.loads(railway_json.read_text(encoding="utf-8"))
    assert railway_data["build"]["builder"] == "RAILPACK"
    assert railway_data["deploy"]["startCommand"].startswith("uvicorn backend.app:app")
    assert railway_data["deploy"]["healthcheckPath"] == "/api/health"

    vercel_json = ROOT_DIR / "vercel.json"
    assert vercel_json.exists(), "Root vercel.json must exist"
    vercel_data = json.loads(vercel_json.read_text(encoding="utf-8"))
    assert vercel_data.get("outputDirectory") == "frontend"

    frontend_vercel_json = ROOT_DIR / "frontend" / "vercel.json"
    assert frontend_vercel_json.exists(), "frontend/vercel.json must exist"

    config_js = ROOT_DIR / "frontend" / "config.js"
    assert config_js.exists(), "frontend/config.js must exist"
    config_content = config_js.read_text(encoding="utf-8")
    assert "getApiBaseUrl" in config_content
    assert "apiUrl" in config_content


def test_requirements_file():
    """Verify requirements.txt contains critical production dependencies."""
    req_file = ROOT_DIR / "requirements.txt"
    assert req_file.exists()
    content = req_file.read_text(encoding="utf-8")
    for dep in ["fastapi", "uvicorn", "pydantic", "sentence-transformers", "rank-bm25", "numpy", "PyJWT", "httpx"]:
        assert dep.lower() in content.lower(), f"Missing {dep} in requirements.txt"
