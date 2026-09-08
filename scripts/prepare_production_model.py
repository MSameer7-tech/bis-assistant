"""
Production Sentence-Transformers Embedding Model Preparation & Pre-cache Script.

Ensures that the required embedding model (sentence-transformers/all-MiniLM-L6-v2)
is fully downloaded and verified at the exact local filesystem path:
    data/models/embeddings/all-MiniLM-L6-v2
BEFORE the FastAPI application starts serving queries.

Guarantees:
1. If the model already exists locally and is valid, uses it directly (offline safe).
2. If absent or incomplete, downloads the model into the exact target path.
3. Performs a sanity encoding test to ensure the model produces valid 384-dim embeddings.
4. Fails loudly with exit code 1 if the download or verification fails, preventing broken deployments.
"""

import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
TARGET_DIR = PROJECT_ROOT / "data" / "models" / "embeddings" / "all-MiniLM-L6-v2"


def is_model_valid(model_path: Path) -> bool:
    """Checks if the local model directory exists and can produce valid embeddings."""
    if not model_path.exists():
        return False

    # Check for essential configuration files
    required_files = ["config.json", "modules.json"]
    for f in required_files:
        if not (model_path / f).exists():
            return False

    # Check weights presence
    has_weights = (
        (model_path / "model.safetensors").exists() or 
        (model_path / "pytorch_model.bin").exists()
    )
    if not has_weights:
        return False

    # Attempt test load and encode
    try:
        from sentence_transformers import SentenceTransformer
        test_model = SentenceTransformer(str(model_path), device="cpu")
        emb = test_model.encode(["BIS production model sanity test"])
        if emb is not None and hasattr(emb, "shape") and len(emb.shape) == 2 and emb.shape[1] == 384:
            return True
    except Exception as e:
        print(f"[ModelPrep] Local model validation check failed: {e}")
        return False

    return False


def prepare_model():
    print("=" * 60)
    print("BIS Production Embedding Model Preparation")
    print(f"Target Path: {TARGET_DIR}")
    print(f"Model: {MODEL_NAME}")
    print("=" * 60)

    # 1. Check if model already exists and is valid
    if is_model_valid(TARGET_DIR):
        print(f"[ModelPrep] OK: Local model already exists and is valid at: {TARGET_DIR}")
        print("[ModelPrep] Ready for production use without network requests.")
        return

    print(f"[ModelPrep] Local model not found or incomplete. Downloading from HuggingFace...")
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    download_success = False
    error_details = []

    # Strategy 1: huggingface_hub snapshot_download (fast, lightweight, ignores unneeded weights)
    try:
        print("[ModelPrep] Attempting snapshot_download via huggingface_hub...")
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id=MODEL_NAME,
            local_dir=str(TARGET_DIR),
            ignore_patterns=[
                "*.h5", "*.ot", "onnx/*", "openvino/*", "*.msgpack", 
                "rust_model.ot", "tf_model.h5"
            ],
            local_dir_use_symlinks=False
        )
        download_success = True
        print("[ModelPrep] Snapshot download completed.")
    except Exception as e:
        print(f"[ModelPrep] snapshot_download failed: {e}")
        error_details.append(f"snapshot_download error: {e}")

    # Strategy 2: SentenceTransformer download and save
    if not download_success:
        try:
            print("[ModelPrep] Falling back to SentenceTransformer.save()...")
            from sentence_transformers import SentenceTransformer
            st_model = SentenceTransformer(MODEL_NAME, device="cpu")
            st_model.save(str(TARGET_DIR))
            download_success = True
            print("[ModelPrep] SentenceTransformer.save() completed.")
        except Exception as e:
            print(f"[ModelPrep] SentenceTransformer.save() failed: {e}")
            error_details.append(f"SentenceTransformer error: {e}")

    if not download_success:
        print(f"\n[FATAL] Failed to download {MODEL_NAME} during build!")
        for err in error_details:
            print(f"  - {err}")
        print("[FATAL] Deployment cannot proceed without the required embedding model.")
        sys.exit(1)

    # 2. Final verification of downloaded model
    print("[ModelPrep] Verifying downloaded model integrity...")
    if not is_model_valid(TARGET_DIR):
        print(f"\n[FATAL] Model downloaded to {TARGET_DIR} but failed validation check!")
        sys.exit(1)

    print(f"[ModelPrep] OK: Model {MODEL_NAME} successfully prepared and verified at: {TARGET_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    prepare_model()
