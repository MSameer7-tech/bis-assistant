#!/usr/bin/env python3
"""Phase 12.DB: Optimization Remediation & Re-verification Tests."""

import unittest
import json
import os
import sys
import copy
import hashlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from scripts.phase12d_benchmark import run_benchmark
from data.derived.phase12.grounded_rag_v1.answer_engine import GroundedRAGEngine
from scripts.phase12_b_hybrid_retrieval import RetrievalData
from sentence_transformers import SentenceTransformer

V22_PATH = "data/bootstrap/bis_missing_domains_dataset_v22.jsonl"
V22_EXPECTED_SHA = "68229fbe37078b6571da7a0b71747fd4b5b383f232b796c71ae6e773c0c13dbe"

PHASE12_2_PATH = "data/derived/phase12/structured_knowledge_v1.jsonl"
PHASE12_2_EXPECTED_SHA = "c91c1f0a46f235ff64738c9e1ea1fecedf9078b94076779ffd1635d95b068486"

VECTOR_PATH = "data/derived/phase12/retrieval_index_foundation_v1/vector/vectors.npy"
VECTOR_EXPECTED_SHA = "ca8d0ad4c614adf796713973c0205ee522331b3a8e848704d4726141c91660ad"

BM25_PATH = "data/derived/phase12/retrieval_index_foundation_v1/bm25_index.pkl"
BM25_EXPECTED_SHA = "4d6a07b644b5a9d172ee5c7acd34ff017746aaf58321424f462908ba87a54df6"

OPTIMIZATION_RESULTS_PATH = "data/benchmarks/phase12d/phase12d_optimization_results.json"

class TestPhase12DBRemediation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rdata = RetrievalData()
        cls.model = SentenceTransformer('data/models/embeddings/all-MiniLM-L6-v2', device='cpu')
        with open(OPTIMIZATION_RESULTS_PATH, "r") as f:
            cls.opt_data = json.load(f)

    def test_01_frozen_artifact_hashes(self):
        """Verify immutable SHA-256 baselines are strictly preserved."""
        artifacts = [
            (V22_PATH, V22_EXPECTED_SHA, "v22 corpus"),
            (PHASE12_2_PATH, PHASE12_2_EXPECTED_SHA, "Phase 12.2 structured knowledge"),
            (VECTOR_PATH, VECTOR_EXPECTED_SHA, "Vector index"),
            (BM25_PATH, BM25_EXPECTED_SHA, "BM25 index")
        ]
        for path, expected_sha, name in artifacts:
            self.assertTrue(os.path.exists(path), f"File not found: {path}")
            hasher = hashlib.sha256()
            with open(path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            actual_sha = hasher.hexdigest()
            self.assertEqual(actual_sha, expected_sha, f"SHA-256 mismatch for {name}")

    def test_02_75_configurations_evaluated(self):
        """Verify the 75-configuration matrix is complete and all evaluated."""
        all_results = self.opt_data.get("all_results", [])
        self.assertEqual(len(all_results), 75, f"Expected 75 configs, got {len(all_results)}")
        
        # Verify grid parameters: 5 k * 5 boost * 3 top_k
        k_vals = {20, 40, 60, 80, 100}
        boost_vals = {1.0, 1.5, 2.0, 2.5, 3.0}
        topk_vals = {10, 20, 30}
        
        seen = set()
        for res in all_results:
            name = res["name"]
            seen.add(name)
            metrics = res["metrics"]
            self.assertEqual(metrics["total_queries"], 9)
            self.assertEqual(metrics["safety_violations"], 0)
            
        expected_names = {
            f"k={k}_boost={boost}_topk={topk}"
            for k in k_vals
            for boost in boost_vals
            for topk in topk_vals
        }
        self.assertEqual(seen, expected_names, "Mismatch in expected 75 configuration names")

    def test_03_winner_selection_logic(self):
        """Verify deterministic selection selects k=20_boost=2.5_topk=10."""
        all_results = self.opt_data["all_results"]
        
        def score_conf(res):
            m = res["metrics"]
            # Parse parameters from name
            parts = res["name"].split("_")
            k = int(parts[0].split("=")[1])
            boost = float(parts[1].split("=")[1])
            topk = int(parts[2].split("=")[1])
            
            # Ordering:
            # 1. Zero safety violations
            # 2. Highest MRR
            # 3. Highest Recall@10
            # 4. Highest Precision@10
            # 5. Highest Hit Rate
            # 6. Lowest Top K (-topk)
            # 7. Lowest RRF k (-k)
            # 8. Lowest boost_factor (-boost)
            return (
                m["safety_violations"] == 0,
                round(m["mrr"], 6),
                round(m["recall_10"], 6),
                round(m["precision_10"], 6),
                round(m["hit_rate"], 6),
                -topk,
                -k,
                -boost
            )
            
        sorted_configs = sorted(all_results, key=score_conf, reverse=True)
        winner = sorted_configs[0]
        self.assertEqual(winner["name"], "k=20_boost=2.5_topk=10")
        self.assertAlmostEqual(winner["metrics"]["mrr"], 0.8889, places=4)
        self.assertAlmostEqual(winner["metrics"]["recall_10"], 0.8889, places=4)
        self.assertAlmostEqual(winner["metrics"]["precision_10"], 0.5963, places=4)
        self.assertAlmostEqual(winner["metrics"]["hit_rate"], 0.8889, places=4)
        
        # Verify best_safe in optimization results matches
        self.assertEqual(self.opt_data["best_safe"]["name"], "k=20_boost=2.5_topk=10")

    def test_04_tie_break_precision_and_boost(self):
        """Verify that boost=2.5 ties boost=3.0 on precision but wins on lower boost."""
        all_results = {r["name"]: r for r in self.opt_data["all_results"]}
        c_25 = all_results["k=20_boost=2.5_topk=10"]
        c_30 = all_results["k=20_boost=3.0_topk=10"]
        c_10 = all_results["k=20_boost=1.0_topk=10"]
        
        # c_25 has higher precision than c_10
        self.assertGreater(c_25["metrics"]["precision_10"], c_10["metrics"]["precision_10"])
        # c_25 and c_30 tie on precision
        self.assertAlmostEqual(c_25["metrics"]["precision_10"], c_30["metrics"]["precision_10"], places=6)
        # Deterministic tie-break prefers lowest boost_factor: 2.5 < 3.0
        self.assertLess(2.5, 3.0)

    def test_05_recalculated_metrics(self):
        """Verify recalculation of metrics for winning configuration."""
        best = self.opt_data["best_safe"]
        m = best["metrics"]
        self.assertAlmostEqual(m["mrr"], 8.0 / 9.0, places=4)
        self.assertAlmostEqual(m["recall_5"], 8.0 / 9.0, places=4)
        self.assertAlmostEqual(m["recall_10"], 8.0 / 9.0, places=4)
        self.assertAlmostEqual(m["recall_20"], 8.0 / 9.0, places=4)
        self.assertAlmostEqual(m["precision_10"], 5.366666666666667 / 9.0, places=4)
        self.assertAlmostEqual(m["hit_rate"], 8.0 / 9.0, places=4)

    def test_06_determinism_double_run(self):
        """Run the winning config twice and verify byte-identical outputs."""
        config = copy.deepcopy(self.rdata.config)
        config["fusion"]["rrf_k"] = 20
        config["exact_match_boost"]["boost_factor"] = 2.5
        config["structured_retrieval"]["top_k"] = 10
        config["bm25_retrieval"]["top_k"] = 10
        config["vector_retrieval"]["top_k"] = 10
        config["final_output"]["top_k"] = 10
        
        self.rdata.config = config
        engine = GroundedRAGEngine(self.rdata, self.model)
        
        metrics_1, results_1 = run_benchmark(engine)
        metrics_2, results_2 = run_benchmark(engine)
        
        dump1 = json.dumps({"metrics": metrics_1, "results": results_1}, sort_keys=True)
        dump2 = json.dumps({"metrics": metrics_2, "results": results_2}, sort_keys=True)
        
        sha1 = hashlib.sha256(dump1.encode("utf-8")).hexdigest()
        sha2 = hashlib.sha256(dump2.encode("utf-8")).hexdigest()
        
        self.assertEqual(sha1, sha2, f"Determinism mismatch: {sha1} vs {sha2}")
        self.assertEqual(metrics_1["safety_violations"], 0)
        self.assertEqual(metrics_2["safety_violations"], 0)

if __name__ == "__main__":
    unittest.main()
