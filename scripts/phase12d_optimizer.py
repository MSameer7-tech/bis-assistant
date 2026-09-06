import json
import os
import copy
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.phase12d_benchmark import run_benchmark
from data.derived.phase12.grounded_rag_v1.answer_engine import GroundedRAGEngine
from scripts.phase12_b_hybrid_retrieval import RetrievalData
from sentence_transformers import SentenceTransformer

def main():
    base_config_path = "data/derived/phase12/hybrid_retrieval_v1/retrieval_config.json"
    with open(base_config_path, "r") as f:
        base_config = json.load(f)

    # 75-configuration sweep matrix:
    # 5 RRF k * 5 Boost * 3 Top K = 75 configurations
    k_values = [20, 40, 60, 80, 100]
    boost_values = [1.0, 1.5, 2.0, 2.5, 3.0]
    top_k_values = [10, 20, 30]

    configs = []
    
    for k in k_values:
        for boost in boost_values:
            for top_k in top_k_values:
                config = copy.deepcopy(base_config)
                config["fusion"]["rrf_k"] = k
                config["exact_match_boost"]["boost_factor"] = float(boost)
                config["structured_retrieval"]["top_k"] = top_k
                config["bm25_retrieval"]["top_k"] = top_k
                config["vector_retrieval"]["top_k"] = top_k
                config["final_output"]["top_k"] = top_k
                
                configs.append({
                    "name": f"k={k}_boost={boost}_topk={top_k}",
                    "k": k,
                    "boost": boost,
                    "top_k": top_k,
                    "config": config
                })

    print(f"Starting optimization sweep over {len(configs)} configurations...")
    
    # Initialize Engine once
    rdata = RetrievalData()
    model = SentenceTransformer('data/models/embeddings/all-MiniLM-L6-v2', device='cpu')
    
    results = []
    best_config = None
    best_score = None
    baseline_result = None

    for idx, conf in enumerate(configs):
        print(f"[{idx+1}/{len(configs)}] Evaluating {conf['name']}...")
        rdata.config = conf["config"]
        engine = GroundedRAGEngine(rdata, model)
        metrics, _ = run_benchmark(engine)
        
        conf_result = {
            "name": conf["name"],
            "metrics": metrics,
            "config": conf["config"],
            "rejected": metrics["safety_violations"] > 0
        }
        
        if conf["k"] == 60 and conf["boost"] == 2.0 and conf["top_k"] == 20:
            baseline_result = conf_result
            
        results.append(conf_result)
        
        # Deterministic objective selection ordering:
        # 1. Zero safety violations
        # 2. Highest MRR
        # 3. Highest Recall@10
        # 4. Highest Precision@10
        # 5. Highest Hit Rate
        # 6. Lowest Top K (-top_k)
        # 7. Lowest RRF k (-k)
        # 8. Lowest boost_factor (-boost)
        score = (
            not conf_result["rejected"],
            round(metrics["mrr"], 6),
            round(metrics["recall_10"], 6),
            round(metrics["precision_10"], 6),
            round(metrics["hit_rate"], 6),
            -conf["top_k"],
            -conf["k"],
            -conf["boost"]
        )
        
        if not conf_result["rejected"]:
            if best_score is None or score > best_score:
                best_score = score
                best_config = conf_result
            
    if not best_config:
        print("WARNING: No strictly safe configuration found. Check safety constraints.")
        best_config = baseline_result
        
    print(f"\nSweep Complete across {len(results)} configurations.")
    if baseline_result:
        print(f"Baseline MRR: {baseline_result['metrics']['mrr']:.4f} (Violations: {baseline_result['metrics']['safety_violations']})")
    print(f"Best Safe Config: {best_config['name']} with MRR: {best_config['metrics']['mrr']:.4f}, Precision@10: {best_config['metrics']['precision_10']:.4f}")
    
    # Save the report data
    report_data = {
        "baseline": baseline_result,
        "best_safe": best_config,
        "all_results": results
    }
    
    with open("data/benchmarks/phase12d/phase12d_optimization_results.json", "w") as f:
        json.dump(report_data, f, indent=2)
        
    print("Optimization results saved to data/benchmarks/phase12d/phase12d_optimization_results.json")

if __name__ == "__main__":
    main()
