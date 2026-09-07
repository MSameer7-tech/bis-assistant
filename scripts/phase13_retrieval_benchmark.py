#!/usr/bin/env python3
"""
Phase 13: Retrieval Benchmarking Suite

Systematically evaluates Phase 13 hybrid retrieval parameters across:
- rrf_k in [20, 40, 60]
- boost_factor in [1.5, 2.0, 2.5, 3.0]
- top_k in [5, 10, 20]

Evaluates against gold benchmark query sets:
1. Standard lookup (e.g. IS 10500, IS 4985, IS 16102, IS 694)
2. Normative clause lookup (e.g. Clause 5.1 TDS, Clause 8.1 Hydrostatic)
3. Operational manual requirements (e.g. UPVC pipe grouping, factory testing)
4. Regulatory QCO / Gazette mandates (e.g. mandatory certification)
5. Laboratory scope & fees (e.g. Lab 112 scope, water heater testing fee)
6. Honest abstention validation (e.g. IS 8978 technical clause query MUST yield is_lims_only=True and ZERO fabricated clauses)

Saves results to data/derived/phase13/retrieval_benchmark_results.json.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.phase13_hybrid_retrieval import (
    Phase13RetrievalData,
    Phase13HybridRetrievalEngine,
    canonical_std
)

BENCHMARK_OUTPUT = PROJECT_ROOT / "data/derived/phase13/retrieval_benchmark_results.json"

BENCHMARK_QUERIES = [
    {
        "id": "Q1_NORM_10500",
        "category": "NORMATIVE_SPECIFICATION",
        "query": "What is the acceptable limit for total dissolved solids in IS 10500 drinking water?",
        "expected_standard": "IS 10500",
        "expected_clause_hint": "5.1",
        "min_tier": "TIER_1_NORMATIVE",
        "must_abstain": False
    },
    {
        "id": "Q2_NORM_4985",
        "category": "NORMATIVE_TEST",
        "query": "Hydrostatic pressure test requirements under IS 4985",
        "expected_standard": "IS 4985",
        "expected_clause_hint": "8.1",
        "min_tier": "TIER_1_NORMATIVE",
        "must_abstain": False
    },
    {
        "id": "Q3_NORM_16102",
        "category": "NORMATIVE_SAFETY",
        "query": "Safety requirements for self-ballasted LED lamps under IS 16102 Part 1",
        "expected_standard": "IS 16102 Part 1",
        "expected_clause_hint": "4",
        "min_tier": "TIER_1_NORMATIVE",
        "must_abstain": False
    },
    {
        "id": "Q4_OPER_4985",
        "category": "OPERATIONAL_GROUPING",
        "query": "Product manual grouping guidelines and sampling for UPVC pipes IS 4985",
        "expected_standard": "IS 4985",
        "expected_clause_hint": None,
        "min_tier": "TIER_1_NORMATIVE",
        "must_abstain": False
    },
    {
        "id": "Q5_REG_QCO",
        "category": "REGULATORY_QCO",
        "query": "Quality control order mandatory certification for electrical appliances and cables",
        "expected_standard": None,
        "expected_clause_hint": None,
        "min_tier": "TIER_1_REGULATORY",
        "must_abstain": False
    },
    {
        "id": "Q6_LIMS_8978",
        "category": "LIMS_SCOPE_AND_FEES",
        "query": "Laboratories testing water heaters according to IS 8978",
        "expected_standard": "IS 8978",
        "expected_clause_hint": None,
        "min_tier": "TIER_2_LIMS",
        "must_abstain": False
    },
    {
        "id": "Q7_ABSTAIN_8978_CLAUSE",
        "category": "HONEST_ABSTENTION_LIMS_ONLY",
        "query": "What specific normative clause in IS 8978 defines the thermostat cutout temperature limit?",
        "expected_standard": "IS 8978",
        "expected_clause_hint": None,
        "min_tier": "TIER_2_LIMS",
        "must_abstain": True,
        "expected_depth": "LIMS_SCOPE_FEE_ONLY"
    },
    {
        "id": "Q8_ABSTAIN_NONEXISTENT",
        "category": "HONEST_ABSTENTION_UNKNOWN",
        "query": "What are the test requirements for rocket propellant under IS 99999?",
        "expected_standard": "IS 99999",
        "expected_clause_hint": None,
        "min_tier": None,
        "must_abstain": True,
        "expected_depth": "NOT_IN_CORPUS"
    }
]


def run_benchmark_grid():
    print("=" * 80)
    print("PHASE 13 RETRIEVAL BENCHMARKING GRID")
    print("=" * 80)

    data = Phase13RetrievalData()
    engine = Phase13HybridRetrievalEngine(data)

    rrf_k_candidates = [20, 40, 60]
    boost_candidates = [1.5, 2.0, 2.5, 3.0]
    top_k = 10

    grid_results = []
    best_config = None
    best_score = -1.0

    total_configs = len(rrf_k_candidates) * len(boost_candidates)
    config_idx = 0

    for rrf_k in rrf_k_candidates:
        for boost in boost_candidates:
            config_idx += 1
            print(f"\nEvaluating Config [{config_idx}/{total_configs}]: rrf_k={rrf_k}, boost_factor={boost}...")

            query_evals = []
            mrr_sum = 0.0
            p_at_1_sum = 0.0
            latencies = []
            abstention_success = 0
            abstention_total = 0

            for bq in BENCHMARK_QUERIES:
                t0 = time.time()
                res = engine.search(
                    bq["query"],
                    top_k=top_k,
                    rrf_k=rrf_k,
                    boost_factor=boost
                )
                lat_ms = (time.time() - t0) * 1000
                latencies.append(lat_ms)

                exp_std = bq["expected_standard"]
                must_abstain = bq["must_abstain"]
                top_results = res["results"]

                matched_rank = None
                p_at_1 = 0.0

                if must_abstain:
                    abstention_total += 1
                    # Check that standard coverage correctly signals abstention / lims only / not in corpus
                    cov = res["standard_coverage"].get(exp_std, {})
                    is_lims_or_missing = cov.get("is_lims_only") or cov.get("max_evidence_depth") in ("NOT_IN_CORPUS", "LIMS_SCOPE_FEE_ONLY", "METADATA_ONLY")
                    # Also ensure top results do NOT have fake normative clauses
                    has_fake_clause = False
                    for r in top_results:
                        if exp_std and canonical_std(r.get("standard_number")) == exp_std:
                            if r.get("authority_tier") == "TIER_1_NORMATIVE" and not cov.get("has_normative_clauses"):
                                has_fake_clause = True

                    if is_lims_or_missing and not has_fake_clause:
                        abstention_success += 1
                        mrr_sum += 1.0
                        p_at_1_sum += 1.0
                else:
                    for rank, r in enumerate(top_results, 1):
                        r_std = canonical_std(r.get("standard_number")) if r.get("standard_number") else None
                        std_matches = exp_std is None or (r_std and (exp_std in r_std or r_std in exp_std))
                        tier_matches = bq["min_tier"] is None or r.get("authority_tier") == bq["min_tier"]

                        if std_matches and tier_matches:
                            matched_rank = rank
                            if rank == 1:
                                p_at_1 = 1.0
                            break

                    recip_rank = 1.0 / matched_rank if matched_rank else 0.0
                    mrr_sum += recip_rank
                    p_at_1_sum += p_at_1

                query_evals.append({
                    "query_id": bq["id"],
                    "category": bq["category"],
                    "matched_rank": matched_rank,
                    "latency_ms": round(lat_ms, 2)
                })

            total_q = len(BENCHMARK_QUERIES)
            avg_mrr = round(mrr_sum / total_q, 4)
            avg_p_at_1 = round(p_at_1_sum / total_q, 4)
            avg_latency = round(sum(latencies) / len(latencies), 2)
            p95_latency = round(sorted(latencies)[int(0.95 * len(latencies))], 2)
            abstention_rate = round(abstention_success / abstention_total, 4) if abstention_total else 1.0

            config_metric = {
                "rrf_k": rrf_k,
                "boost_factor": boost,
                "top_k": top_k,
                "mrr": avg_mrr,
                "precision_at_1": avg_p_at_1,
                "abstention_accuracy": abstention_rate,
                "mean_latency_ms": avg_latency,
                "p95_latency_ms": p95_latency,
                "composite_score": round((avg_mrr * 0.45) + (avg_p_at_1 * 0.35) + (abstention_rate * 0.20), 4)
            }
            grid_results.append(config_metric)
            print(f"  -> MRR: {avg_mrr:.4f} | P@1: {avg_p_at_1:.4f} | Abstention: {abstention_rate*100:.1f}% | Latency: {avg_latency:.1f}ms | Composite: {config_metric['composite_score']:.4f}")

            if config_metric["composite_score"] > best_score:
                best_score = config_metric["composite_score"]
                best_config = config_metric

    # Sort results by composite score desc
    grid_results.sort(key=lambda x: -x["composite_score"])

    benchmark_payload = {
        "benchmark_version": "v13.0",
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_configurations_tested": len(grid_results),
        "benchmark_query_count": len(BENCHMARK_QUERIES),
        "optimal_configuration": best_config,
        "grid_results": grid_results
    }

    BENCHMARK_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(BENCHMARK_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(benchmark_payload, f, indent=2)

    print("\n" + "=" * 80)
    print("BENCHMARK COMPLETED")
    print(f"Optimal Configuration: rrf_k={best_config['rrf_k']}, boost_factor={best_config['boost_factor']}, top_k={best_config['top_k']}")
    print(f"Performance: MRR={best_config['mrr']}, P@1={best_config['precision_at_1']}, Abstention Accuracy={best_config['abstention_accuracy']*100}%")
    print(f"Latency: Mean={best_config['mean_latency_ms']}ms, P95={best_config['p95_latency_ms']}ms")
    print(f"Saved results to {BENCHMARK_OUTPUT}")
    print("=" * 80)


if __name__ == "__main__":
    run_benchmark_grid()
