#!/usr/bin/env python3
"""Phase 12.E: Production Integration & Release Hardening Tests."""

import unittest
import json
import os
import sys
import hashlib
from pathlib import Path

# Ensure root directory is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.phase12_e_production_rag import get_production_engine, query_production_rag

V22_PATH = "data/bootstrap/bis_missing_domains_dataset_v22.jsonl"
V22_EXPECTED_SHA = "68229fbe37078b6571da7a0b71747fd4b5b383f232b796c71ae6e773c0c13dbe"

PHASE12_2_PATH = "data/derived/phase12/structured_knowledge_v1.jsonl"
PHASE12_2_EXPECTED_SHA = "c91c1f0a46f235ff64738c9e1ea1fecedf9078b94076779ffd1635d95b068486"

VECTOR_PATH = "data/derived/phase12/retrieval_index_foundation_v1/vector/vectors.npy"
VECTOR_EXPECTED_SHA = "ca8d0ad4c614adf796713973c0205ee522331b3a8e848704d4726141c91660ad"

BM25_PATH = "data/derived/phase12/retrieval_index_foundation_v1/bm25_index.pkl"
BM25_EXPECTED_SHA = "4d6a07b644b5a9d172ee5c7acd34ff017746aaf58321424f462908ba87a54df6"

class TestPhase12EProduction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = get_production_engine()

    def test_01_frozen_artifact_immutability(self):
        """Verify immutable SHA-256 baselines remain unmodified in Phase 12.E."""
        artifacts = [
            (V22_PATH, V22_EXPECTED_SHA, "v22 corpus"),
            (PHASE12_2_PATH, PHASE12_2_EXPECTED_SHA, "Phase 12.2 knowledge"),
            (VECTOR_PATH, VECTOR_EXPECTED_SHA, "Vector index"),
            (BM25_PATH, BM25_EXPECTED_SHA, "BM25 index")
        ]
        for path, expected_sha, name in artifacts:
            self.assertTrue(os.path.exists(path), f"Missing artifact: {path}")
            hasher = hashlib.sha256()
            with open(path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            self.assertEqual(hasher.hexdigest(), expected_sha, f"SHA mismatch for {name}")

    def test_02_production_configuration_propagation(self):
        """Verify the verified optimal configuration (rrf_k=20, boost=2.5, top_k=10) is active."""
        cfg = self.engine.retrieval_data.config
        self.assertEqual(cfg["fusion"]["rrf_k"], 20)
        self.assertEqual(cfg["exact_match_boost"]["boost_factor"], 2.5)
        self.assertEqual(cfg["structured_retrieval"]["top_k"], 10)
        self.assertEqual(cfg["bm25_retrieval"]["top_k"], 10)
        self.assertEqual(cfg["vector_retrieval"]["top_k"], 10)
        self.assertEqual(cfg["final_output"]["top_k"], 10)

    def test_03_response_schema_contract(self):
        """Verify production responses strictly adhere to the contract schema."""
        res = query_production_rag("What is IS 8978?", self.engine)
        required_keys = ["status", "answer", "claims", "evidence", "citations", "entities", "subquestions", "confidence", "provenance"]
        for k in required_keys:
            self.assertIn(k, res, f"Missing key in response contract: {k}")
        self.assertEqual(res["confidence"], "BASELINE_UNCALIBRATED")
        self.assertIn(res["status"], ["SUFFICIENT", "PARTIAL", "INSUFFICIENT"])
        self.assertIsInstance(res["claims"], list)
        self.assertIsInstance(res["evidence"], list)
        self.assertIsInstance(res["citations"], list)
        self.assertIsInstance(res["entities"], list)

    def test_04_sufficient_query_behavior(self):
        """Verify known standard queries return SUFFICIENT with grounded evidence."""
        res = query_production_rag("What is IS 8978?", self.engine)
        self.assertEqual(res["status"], "SUFFICIENT")
        self.assertTrue(len(res["evidence"]) > 0)
        self.assertIn("IS 8978", res["answer"])

    def test_05_partial_fee_behavior(self):
        """Verify testing fee queries with lab-only fee records return PARTIAL."""
        res = query_production_rag("What is the testing fee for IS 8978?", self.engine)
        self.assertEqual(res["status"], "PARTIAL")
        self.assertIn("partial", res["answer"].lower())

    def test_06_insufficient_missing_corpus_behavior(self):
        """Verify queries for entities absent from v22 return INSUFFICIENT without hallucination."""
        # IS 616 is deliberately absent from v22
        res = query_production_rag("What is IS 999999?", self.engine)
        self.assertEqual(res["status"], "INSUFFICIENT")
        self.assertIn("could not verify", res["answer"].lower())

        # Unknown standard
        res_unknown = query_production_rag("What is IS 999999?", self.engine)
        self.assertEqual(res_unknown["status"], "INSUFFICIENT")

        # Unknown laboratory
        res_lab = query_production_rag("What is LAB-UNKNOWN_79dcb12d?", self.engine)
        self.assertEqual(res_lab["status"], "INSUFFICIENT")

    def test_07_determinism(self):
        """Verify byte-identical determinism across two sequential passes."""
        q = "Which laboratories explicitly have scope for IS 8978?"
        res1 = query_production_rag(q, self.engine)
        res2 = query_production_rag(q, self.engine)

        dump1 = json.dumps(res1, sort_keys=True)
        dump2 = json.dumps(res2, sort_keys=True)
        sha1 = hashlib.sha256(dump1.encode("utf-8")).hexdigest()
        sha2 = hashlib.sha256(dump2.encode("utf-8")).hexdigest()
        self.assertEqual(sha1, sha2, "Determinism violated in production pipeline")

if __name__ == "__main__":
    unittest.main()
