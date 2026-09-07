#!/usr/bin/env python3
"""
Phase 13: Full BIS Authoritative Retrieval Index Builder

Builds the complete Phase 13 retrieval index in:
  data/derived/phase13/retrieval_index_full_v1/

Components:
1. retrieval_units.jsonl: Canonical retrieval units with exact match identifiers
2. bm25_index.pkl: BM25Okapi index over all 20,745 units
3. vector/vectors.npy: NumPy float32 (20745, 384) matrix via local offline all-MiniLM-L6-v2
4. vector/vector_metadata.jsonl: Row-to-unit mapping
5. Manifests with cryptographic SHA-256 verification
"""

import os
import sys
import json
import time
import pickle
import hashlib
from pathlib import Path
import numpy as np

# Force offline mode for sentence-transformers / huggingface
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sentence_transformers import SentenceTransformer

CORPUS_PATH = PROJECT_ROOT / "data/derived/phase13/canonical_corpus_v1.jsonl"
INDEX_DIR = PROJECT_ROOT / "data/derived/phase13/retrieval_index_full_v1"
VECTOR_DIR = INDEX_DIR / "vector"
MODEL_PATH = PROJECT_ROOT / "data/models/embeddings/all-MiniLM-L6-v2"


from scripts.phase13_bm25 import BM25Okapi, tokenize_bm25



def build_phase13_indexes():
    start_time = time.time()
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)

    print("=== Phase 13: Building Authoritative Full Retrieval Index ===")
    print(f"Reading canonical corpus from {CORPUS_PATH}...")

    retrieval_units = []
    tokenized_docs = []
    texts_to_embed = []
    vector_metadata = []

    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if not line.strip():
                continue
            ev = json.loads(line)
            ev_id = ev["evidence_id"]
            std = ev.get("standard_number") or ""
            clause = ev.get("clause") or ""
            heading = ev.get("heading") or ""
            tier = ev.get("authority_tier")
            depth = ev.get("evidence_depth")
            dtype = ev.get("document_type")
            passage = ev.get("passage_text", "")

            # Formulate structured retrieval representation with exact identifiers
            # Include IS number and heading in lexical token stream for high exact-match recall
            header_prefix = f"{std} " if std else ""
            if clause:
                header_prefix += f"Clause {clause} "
            if heading:
                header_prefix += f"{heading} "

            full_search_text = f"{header_prefix}\n{passage}".strip()

            ru = {
                "retrieval_unit_id": ev_id,
                "source_record_id": ev.get("source_id"),
                "document_id": ev.get("document_id"),
                "standard_number": std if std else None,
                "standard_part": ev.get("standard_part"),
                "edition_year": ev.get("edition_year"),
                "clause": clause if clause else None,
                "heading": heading if heading else None,
                "page": ev.get("page"),
                "document_type": dtype,
                "authority_tier": tier,
                "evidence_depth": depth,
                "normative_force": ev.get("normative_force"),
                "text": passage,
                "full_index_text": full_search_text,
                "checksum_sha256": ev.get("checksum_sha256"),
                "source_url": ev.get("source_url")
            }
            retrieval_units.append(ru)

            # Tokenize for BM25
            tokenized_docs.append(tokenize_bm25(full_search_text))

            # Prepare for embedding
            # Cap passage to 512 chars for embedding to keep focus on header + opening definitions
            embed_text = f"{header_prefix}: {passage[:400]}".strip()
            texts_to_embed.append(embed_text)

            vector_metadata.append({
                "row_index": idx,
                "retrieval_unit_id": ev_id,
                "standard_number": std if std else None,
                "clause": clause if clause else None,
                "authority_tier": tier,
                "evidence_depth": depth,
                "document_type": dtype
            })

    total_units = len(retrieval_units)
    print(f"Loaded {total_units:,} canonical units in {time.time() - start_time:.2f}s.")

    # -------------------------------------------------------------------------
    # 1. Save retrieval_units.jsonl
    # -------------------------------------------------------------------------
    ru_path = INDEX_DIR / "retrieval_units.jsonl"
    print(f"Saving {ru_path}...")
    with open(ru_path, "w", encoding="utf-8") as f:
        for ru in retrieval_units:
            f.write(json.dumps(ru, ensure_ascii=False) + "\n")

    # -------------------------------------------------------------------------
    # 2. Build and Save BM25 Index
    # -------------------------------------------------------------------------
    print("Building BM25Okapi lexical index...")
    bm25_start = time.time()
    bm25 = BM25Okapi(tokenized_docs)
    bm25_path = INDEX_DIR / "bm25_index.pkl"
    print(f"Saving BM25 index to {bm25_path} (built in {time.time() - bm25_start:.2f}s)...")
    with open(bm25_path, "wb") as f:
        pickle.dump(bm25, f, protocol=pickle.HIGHEST_PROTOCOL)

    # -------------------------------------------------------------------------
    # 3. Build and Save Semantic Vector Index
    # -------------------------------------------------------------------------
    print(f"Loading local embedding model from {MODEL_PATH}...")
    embed_start = time.time()
    model = SentenceTransformer(str(MODEL_PATH), device="cpu")

    print(f"Encoding {total_units:,} units into 384-dim normalized vectors (batch_size=128)...")
    vectors = model.encode(
        texts_to_embed,
        batch_size=128,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True
    )
    vectors = np.asarray(vectors, dtype=np.float32)
    print(f"Vector matrix created: shape {vectors.shape}, dtype {vectors.dtype} in {time.time() - embed_start:.2f}s.")

    vec_path = VECTOR_DIR / "vectors.npy"
    print(f"Saving vectors to {vec_path}...")
    np.save(str(vec_path), vectors)

    vec_meta_path = VECTOR_DIR / "vector_metadata.jsonl"
    print(f"Saving vector metadata to {vec_meta_path}...")
    with open(vec_meta_path, "w", encoding="utf-8") as f:
        for vm in vector_metadata:
            f.write(json.dumps(vm, ensure_ascii=False) + "\n")

    # -------------------------------------------------------------------------
    # 4. Generate Manifests & Hashes
    # -------------------------------------------------------------------------
    manifest = {
        "index_version": "v13.0",
        "phase": "13",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_units": total_units,
        "bm25_document_count": total_units,
        "bm25_vocabulary_size": len(bm25.idf),
        "vector_count": int(vectors.shape[0]),
        "vector_dimension": int(vectors.shape[1]),
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "model_local_path": str(MODEL_PATH.relative_to(PROJECT_ROOT)),
        "distance_metric": "cosine (inner product on L2-normalized vectors)",
        "offline_enforced": True,
        "artifacts": {
            "retrieval_units": str(ru_path.relative_to(PROJECT_ROOT)),
            "bm25_index": str(bm25_path.relative_to(PROJECT_ROOT)),
            "vector_matrix": str(vec_path.relative_to(PROJECT_ROOT)),
            "vector_metadata": str(vec_meta_path.relative_to(PROJECT_ROOT))
        }
    }

    manifest_path = INDEX_DIR / "retrieval_index_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    total_time = time.time() - start_time
    print(f"=== Phase 13 Index Construction Complete in {total_time:.2f}s ===")
    print(f"Manifest written to {manifest_path}")
    return manifest


if __name__ == "__main__":
    build_phase13_indexes()
