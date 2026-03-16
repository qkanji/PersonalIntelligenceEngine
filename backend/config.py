from pathlib import Path
from functools import lru_cache
import os

# ── Environment helpers ──────────────────────────────────────────────────────

def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


# ── Settings ─────────────────────────────────────────────────────────────────

# Pinecone
PINECONE_API_KEY:   str = _env("PINECONE_API_KEY")  # set via env; NEVER hard-code
PINECONE_INDEX:     str = _env("PINECONE_INDEX", "qayim-bge-m3-index")

# Embedding model (runs on CPU to leave VRAM for the LLM)
EMBED_MODEL_ID:     str = _env("EMBED_MODEL_ID", "BAAI/bge-m3")
EMBED_DEVICE:       str = _env("EMBED_DEVICE", "cpu")

# LLM (4-bit on GPU)
LLM_MODEL_ID:       str = _env("LLM_MODEL_ID", "Qwen/Qwen2.5-3B-Instruct")
LLM_DEVICE:         str = _env("LLM_DEVICE", "cuda")
MAX_NEW_TOKENS:     int = int(_env("MAX_NEW_TOKENS", "1024"))

# RAG retrieval
TOP_K:              int = int(_env("TOP_K", "8"))

# User (for multi-user Pinecone filtering)
CURRENT_USER_EMAIL: str = _env("CURRENT_USER_EMAIL", "")

# CORS
FRONTEND_ORIGIN:    str = _env("FRONTEND_ORIGIN", "http://localhost:5173")
