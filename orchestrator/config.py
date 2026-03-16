"""
Orchestrator configuration — reads everything from environment variables.
"""

import os


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _required_env(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val


# ── RunPod ──────────────────────────────────────────────────────────────────
RUNPOD_API_KEY: str = _required_env("RUNPOD_API_KEY")

# GPU pod template
RUNPOD_GPU_TYPE: str = _env("RUNPOD_GPU_TYPE", "NVIDIA GeForce RTX 4090")
# Community image: CUDA 12.4 + torch 2.6.0 — compatible with vllm>=0.8 without
# triggering a torch reinstall.
RUNPOD_IMAGE: str = _env("RUNPOD_IMAGE", "madiator2011/better-pytorch:cuda12.4-torch2.6.0")
RUNPOD_CLOUD_TYPE: str = _env("RUNPOD_CLOUD_TYPE", "SECURE")
# Container disk is ephemeral (destroyed on pod termination) and only billed while running.
# 35 GB covers: base image (~5) + vLLM deps (~7) + Qwen2.5-VL-7B (~14) + BGE-M3 (~2.3) + images (~1.5) + buffer
# No network volume is used — model weights are re-downloaded each run (~1-2 min on RunPod's network).
RUNPOD_CONTAINER_DISK: int = int(_env("RUNPOD_CONTAINER_DISK", "35"))  # GB

# ── Google Cloud ────────────────────────────────────────────────────────────
GCS_BUCKET: str = _env("GCS_BUCKET", "pie-data")
GCP_PROJECT: str = _env("GCP_PROJECT", "personal-intelligence-engine")

# Service account key JSON (base64-encoded) passed to the worker pod
GCP_SA_KEY_JSON_B64: str = _env("GCP_SA_KEY_JSON_B64", "")

# ── Pinecone ────────────────────────────────────────────────────────────────
PINECONE_API_KEY: str = _required_env("PINECONE_API_KEY")
PINECONE_INDEX: str = _env("PINECONE_INDEX", "qayim-bge-m3-index")

# ── Worker bootstrap ───────────────────────────────────────────────────────
# URL or GCS path to download worker.py onto the RunPod container.
# Two supported formats:
#   A) GitHub Gist raw URL (recommended — paste file, click Raw, copy URL):
#      https://gist.githubusercontent.com/<user>/<gist_id>/raw/worker.py
#   B) GCS path (keeps everything in your bucket — upload worker.py to GCS):
#      gs://pie-data/scripts/worker.py
# Google Drive is NOT supported (curl cannot bypass the virus-scan warning page).
WORKER_SCRIPT_URL: str = _env(
    "WORKER_SCRIPT_URL",
    "https://gist.githubusercontent.com/YOUR_GITHUB_USERNAME/YOUR_GIST_ID/raw/worker.py",
)

# Pip packages the worker needs (space-separated)
WORKER_DEPS: str = _env(
    "WORKER_DEPS",
    "vllm==0.17.1 transformers>=4.40.0 sentence-transformers pinecone google-cloud-storage qwen-vl-utils",
)
# ── Pub/Sub (Pull) ──────────────────────────────────────────────────────
PUBSUB_SUBSCRIPTION: str = _env("PUBSUB_SUBSCRIPTION", "rag-jobs-pull")
PUBSUB_PULL_INTERVAL: int = int(_env("PUBSUB_PULL_INTERVAL", "60"))  # seconds between polls
# ── Health-check ────────────────────────────────────────────────────────────
HEALTH_CHECK_INTERVAL: int = int(_env("HEALTH_CHECK_INTERVAL", "60"))  # seconds

