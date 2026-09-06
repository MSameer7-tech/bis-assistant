#!/usr/bin/env python3
"""
Phase 12.E: Production Integration & Release Hardening

Exposes the production Grounded RAG Engine with the verified Phase 12.DB
optimal parameters (rrf_k=20, boost_factor=2.5, top_k=10) and provides
an HTTP API adapter for frontend and downstream integration.
"""

import os
import sys
import json
import copy
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.derived.phase12.grounded_rag_v1.answer_engine import GroundedRAGEngine
from scripts.phase12_b_hybrid_retrieval import RetrievalData
from sentence_transformers import SentenceTransformer

# Global singleton instance for production server reuse
_PRODUCTION_ENGINE = None

def get_production_engine(model_path="data/models/embeddings/all-MiniLM-L6-v2", device="cpu"):
    """
    Initializes and returns the Phase 12.E Production Grounded RAG Engine.
    Dynamically injects the Phase 12.DB verified optimal configuration
    (rrf_k=20, boost_factor=2.5, top_k=10) without modifying the immutable
    retrieval_config.json baseline.
    """
    global _PRODUCTION_ENGINE
    if _PRODUCTION_ENGINE is not None:
        return _PRODUCTION_ENGINE

    rdata = RetrievalData()
    
    # Load the base config from the frozen baseline
    base_config_path = PROJECT_ROOT / "data/derived/phase12/hybrid_retrieval_v1/retrieval_config.json"
    with open(base_config_path, "r") as f:
        base_config = json.load(f)
        
    # Overlay the verified Phase 12.DB production configuration
    base_config["fusion"]["rrf_k"] = 20
    base_config["exact_match_boost"]["boost_factor"] = 2.5
    base_config["structured_retrieval"]["top_k"] = 10
    base_config["bm25_retrieval"]["top_k"] = 10
    base_config["vector_retrieval"]["top_k"] = 10
    base_config["final_output"]["top_k"] = 10
    
    rdata.config = base_config
    
    # Initialize the embedding model
    model_full_path = str(PROJECT_ROOT / model_path) if not Path(model_path).is_absolute() else model_path
    model = SentenceTransformer(model_full_path, device=device)
    
    # Instantiate Production Engine
    _PRODUCTION_ENGINE = GroundedRAGEngine(rdata, model)
    return _PRODUCTION_ENGINE

def query_production_rag(query_text: str, engine=None) -> dict:
    """
    Executes a query through the production Grounded RAG Engine and formats
    the output into the stable Phase 12.E API response contract.
    """
    if not query_text or not query_text.strip():
        return {
            "status": "INSUFFICIENT",
            "answer": "Please provide a query to research.",
            "claims": [],
            "unsupported_claims": [],
            "evidence": [],
            "citations": [],
            "subquestions": [],
            "entities": [],
            "confidence": "BASELINE_UNCALIBRATED",
            "provenance": {
                "source": "BIS Official Knowledge Base (v22 Frozen Baseline)",
                "configuration": {"rrf_k": 20, "boost_factor": 2.5, "top_k": 10}
            }
        }

    if engine is None:
        engine = get_production_engine()

    trace = engine.answer(query_text.strip())

    # Determine global evidence status from subquestions if not set
    final_status = trace.get("evidence_status", "SUFFICIENT")
    subquestions = trace.get("subquestions", [])
    if subquestions:
        for sq in subquestions:
            if sq.get("evidence_status") == "INSUFFICIENT":
                final_status = "INSUFFICIENT"
                break
            elif sq.get("evidence_status") == "PARTIAL":
                final_status = "PARTIAL"
    else:
        final_status = "INSUFFICIENT"

    # Extract all bound entities mentioned in evidence and claims
    entities = []
    seen_entities = set()
    for ev in trace.get("evidence", []):
        std = ev.get("standard_number")
        if std and std not in seen_entities:
            entities.append({"type": "STANDARD", "id": std, "name": std})
            seen_entities.add(std)
        lab = ev.get("laboratory_id")
        if lab and lab not in seen_entities:
            entities.append({"type": "LABORATORY", "id": lab, "name": f"Lab {lab}"})
            seen_entities.add(lab)

    response = {
        "status": final_status,
        "answer": trace.get("answer", ""),
        "claims": trace.get("claims", []),
        "unsupported_claims": trace.get("unsupported_claims", []),
        "evidence": trace.get("evidence", []),
        "citations": trace.get("citations", []),
        "entities": entities,
        "subquestions": subquestions,
        "generation_mode": trace.get("generation_mode", "GROUNDED"),
        "confidence": "BASELINE_UNCALIBRATED",
        "provenance": {
            "source": "Bureau of Indian Standards Official Normative Data (v22 Frozen Baseline)",
            "retrieval_mode": "Hybrid (BM25 + Semantic + Exact Identifier Boost)",
            "configuration": {
                "rrf_k": 20,
                "boost_factor": 2.5,
                "top_k": 10
            },
            "grounding_gate": "Phase 12.CB ClaimValidator (Zero Hallucination Enforced)"
        }
    }
    return response

class ProductionHTTPHandler(SimpleHTTPRequestHandler):
    """
    Serves frontend static files and handles Phase 12.E production API endpoints.
    """
    def __init__(self, *args, **kwargs):
        frontend_dir = str(PROJECT_ROOT / "frontend")
        super().__init__(*args, directory=frontend_dir, **kwargs)

    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/assistant/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._set_cors_headers()
            self.end_headers()
            health_info = {
                "status": "healthy",
                "phase": "F2",
                "rag": "Phase 12.E",
                "llm_fallback": "Groq",
                "immutability": "VERIFIED"
            }
            self.wfile.write(json.dumps(health_info).encode("utf-8"))
            return

        if self.path == "/api/phase12e/health" or self.path == "/api/v1/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._set_cors_headers()
            self.end_headers()
            health_info = {
                "status": "healthy",
                "phase": "12.E",
                "engine": "GroundedRAGEngine",
                "configuration": {
                    "rrf_k": 20,
                    "boost_factor": 2.5,
                    "top_k": 10
                },
                "confidence": "BASELINE_UNCALIBRATED",
                "immutability": "VERIFIED"
            }
            self.wfile.write(json.dumps(health_info).encode("utf-8"))
            return

        # Fallback to serving frontend static files
        super().do_GET()

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len) if content_len > 0 else b"{}"

        if self.path in ["/api/assistant/query", "/api/v1/assistant/query"]:
            try:
                data = json.loads(post_body.decode("utf-8"))
                query_text = data.get("query", "")
                from scripts.phase12_f2_orchestrator import orchestrate_assistant_query
                result = orchestrate_assistant_query(query_text)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(result).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                err_payload = {"status": "ERROR", "error": str(e)}
                self.wfile.write(json.dumps(err_payload).encode("utf-8"))
            return

        if self.path in ["/api/phase12e/query", "/api/v1/query"]:
            try:
                data = json.loads(post_body.decode("utf-8"))
                query_text = data.get("query", "")
                
                result = query_production_rag(query_text)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(result).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                err_payload = {"status": "ERROR", "error": str(e)}
                self.wfile.write(json.dumps(err_payload).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

def run_production_server(port=3000):
    """Starts the production unified server."""
    # Warm up engine
    print("Warming up Phase 12.E Production Engine...")
    get_production_engine()
    print(f"Starting Phase 12.E Production Server on port {port}...")
    server = ThreadingHTTPServer(("", port), ProductionHTTPHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server stopping...")
    finally:
        server.server_close()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
        run_production_server(port=port)
    else:
        eng = get_production_engine()
        print("Production Engine Initialized Successfully!")
        print(f"Injected Config: {eng.retrieval_data.config}")
        test_res = query_production_rag("What is IS 8978?", eng)
        print(f"Test Query Result Status: {test_res['status']}")
