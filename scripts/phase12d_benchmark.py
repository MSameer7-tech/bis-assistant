import json
import os
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.derived.phase12.grounded_rag_v1.answer_engine import GroundedRAGEngine
from scripts.phase12_b_hybrid_retrieval import RetrievalData
from sentence_transformers import SentenceTransformer

def calculate_mrr(evidence_pool, required_entities):
    for rank, ev in enumerate(evidence_pool):
        # Determine if this evidence is relevant
        is_relevant = False
        ev_str = json.dumps(ev)
        for req in required_entities:
            if req in ev_str:
                is_relevant = True
                break
        if is_relevant:
            return 1.0 / (rank + 1)
    return 0.0

def calculate_recall_at_k(evidence_pool, required_entities, k):
    pool_k = evidence_pool[:k]
    for ev in pool_k:
        ev_str = json.dumps(ev)
        for req in required_entities:
            if req in ev_str:
                return 1.0 # Found at least one relevant document in top k
    return 0.0
    
def calculate_precision_at_k(evidence_pool, required_entities, k):
    pool_k = evidence_pool[:k]
    if not pool_k:
        return 0.0
    relevant_count = 0
    for ev in pool_k:
        ev_str = json.dumps(ev)
        for req in required_entities:
            if req in ev_str:
                relevant_count += 1
                break
    return relevant_count / len(pool_k)

def run_benchmark(engine):
    # Load dataset
    QUERIES_FILE = "data/benchmarks/phase12d/phase12d_benchmark_queries.jsonl"
    EXPECTED_FILE = "data/benchmarks/phase12d/phase12d_expected_behaviour.jsonl"
    
    queries = []
    with open(QUERIES_FILE, "r") as f:
        for line in f:
            queries.append(json.loads(line.strip()))
            
    expected = {}
    with open(EXPECTED_FILE, "r") as f:
        for line in f:
            data = json.loads(line.strip())
            expected[data["query_id"]] = data

    metrics = {
        "mrr_sum": 0.0,
        "recall_5_sum": 0.0,
        "recall_10_sum": 0.0,
        "recall_20_sum": 0.0,
        "precision_5_sum": 0.0,
        "precision_10_sum": 0.0,
        "hit_count": 0,
        "total_queries": 0,
        
        # Safety Metrics
        "safety_violations": 0,
        "entity_leakage": 0,
        "wrong_standard_rate": 0,
        "wrong_fee_rate": 0,
        "wrong_lab_rate": 0,
        "unsupported_qco_rate": 0,
        "unsupported_latest_rate": 0,
        "source_title_as_fact": 0,
        "unsupported_relationship": 0
    }

    results = []

    for q_obj in queries:
        qid = q_obj["query_id"]
        q_text = q_obj["query"]
        exp = expected[qid]
        
        # Run query
        trace = engine.answer(q_text)
        evidence_pool = trace.get("evidence", [])
        
        req_ents = exp.get("required_entities", [])
        proh_ents = exp.get("prohibited_entities", [])
        exp_status = exp.get("expected_status")
        
        # 1. Retrieval Metrics (Only calculated if there are required entities)
        if req_ents:
            mrr = calculate_mrr(evidence_pool, req_ents)
            r5 = calculate_recall_at_k(evidence_pool, req_ents, 5)
            r10 = calculate_recall_at_k(evidence_pool, req_ents, 10)
            r20 = calculate_recall_at_k(evidence_pool, req_ents, 20)
            p5 = calculate_precision_at_k(evidence_pool, req_ents, 5)
            p10 = calculate_precision_at_k(evidence_pool, req_ents, 10)
            
            metrics["mrr_sum"] += mrr
            metrics["recall_5_sum"] += r5
            metrics["recall_10_sum"] += r10
            metrics["recall_20_sum"] += r20
            metrics["precision_5_sum"] += p5
            metrics["precision_10_sum"] += p10
            if mrr > 0:
                metrics["hit_count"] += 1
            metrics["total_queries"] += 1

        # 2. Safety Metrics
        violation = False
        entity_leakage_only = False
        
        # Calculate post-validation overall status
        final_status = "SUFFICIENT"
        for sq in trace["subquestions"]:
            if sq["evidence_status"] == "INSUFFICIENT":
                final_status = "INSUFFICIENT"
                break
            elif sq["evidence_status"] == "PARTIAL":
                final_status = "PARTIAL"
        if not trace["subquestions"]:
            final_status = "NO_EVIDENCE"
            
        trace["evidence_status"] = final_status
        
        # A. Expected Status Match
        # If it should be INSUFFICIENT but it's SUFFICIENT
        if exp_status in ["INSUFFICIENT", "NO_EVIDENCE"] and trace["evidence_status"] in ["SUFFICIENT", "PARTIAL"]:
            violation = True
            metrics["safety_violations"] += 1
            # Classify specifically for the report
            if "latest" in q_text.lower() or "revised" in q_text.lower():
                metrics["unsupported_latest_rate"] += 1
            elif "fee" in q_text.lower():
                metrics["wrong_fee_rate"] += 1
            elif "qco" in q_text.lower() or "mandatory" in q_text.lower():
                metrics["unsupported_qco_rate"] += 1
            else:
                metrics["unsupported_relationship"] += 1
        elif exp_status in ["SUFFICIENT", "PARTIAL"] and proh_ents:
             entity_leakage_only = True
                
        # B. Prohibited Entity Leakage
        # The answer text or claims must NOT contain prohibited entities
        answer_text = " ".join([sq["answer_text"] for sq in trace["subquestions"]])
        
        # Add claims to answer_text for robust checking
        for sq in trace["subquestions"]:
             if "claims" in sq:
                 answer_text += " " + " ".join([c["claim"] for c in sq["claims"]])
                 
        for proh in proh_ents:
            if proh.lower() in answer_text.lower():
                violation = True
                metrics["safety_violations"] += 1
                metrics["entity_leakage"] += 1
                if "is " in proh.lower() or "standard" in proh.lower():
                    metrics["wrong_standard_rate"] += 1
                print(f"VIOLATION: Leakage of '{proh}' in Q: '{q_text}'\nAnswer: {answer_text}")
                break
                
        if violation and not entity_leakage_only:
             print(f"VIOLATION: Q: '{q_text}' expected {exp_status} but got {trace['evidence_status']}")
                
        results.append({
            "query_id": qid,
            "query": q_text,
            "status": trace["evidence_status"],
            "expected_status": exp_status,
            "violation": violation
        })

    # Average metrics
    tq = metrics["total_queries"]
    if tq > 0:
        metrics["mrr"] = metrics["mrr_sum"] / tq
        metrics["recall_5"] = metrics["recall_5_sum"] / tq
        metrics["recall_10"] = metrics["recall_10_sum"] / tq
        metrics["recall_20"] = metrics["recall_20_sum"] / tq
        metrics["precision_5"] = metrics["precision_5_sum"] / tq
        metrics["precision_10"] = metrics["precision_10_sum"] / tq
        metrics["hit_rate"] = metrics["hit_count"] / tq
    else:
        metrics["mrr"] = metrics["recall_5"] = metrics["recall_10"] = metrics["recall_20"] = metrics["precision_5"] = metrics["precision_10"] = metrics["hit_rate"] = 0.0

    return metrics, results

if __name__ == "__main__":
    rdata = RetrievalData()
    model = SentenceTransformer('data/models/embeddings/all-MiniLM-L6-v2', device='cpu')
    engine = GroundedRAGEngine(rdata, model)
    metrics, res = run_benchmark(engine)
    print(json.dumps(metrics, indent=2))
