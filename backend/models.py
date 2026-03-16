"""
Singleton model loader.
─────────────────────────
Loads the embedding model and the LLM once, then exposes them as
module-level objects so every FastAPI request re-uses the same instances.
"""

import torch
from sentence_transformers import SentenceTransformer
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)

from . import config

# ── Embedding model (CPU — fast enough for single queries) ───────────────────

print(f"[models] Loading embedding model: {config.EMBED_MODEL_ID} on {config.EMBED_DEVICE}...")
embed_model = SentenceTransformer(config.EMBED_MODEL_ID, device=config.EMBED_DEVICE)
EMBED_DIM: int = embed_model.get_sentence_embedding_dimension()
print(f"[models] Embedding model ready  (dim={EMBED_DIM})")


# ── LLM (4-bit quantised on GPU) ────────────────────────────────────────────

print(f"[models] Loading LLM: {config.LLM_MODEL_ID} on {config.LLM_DEVICE}...")

_bnb = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
)

tokenizer = AutoTokenizer.from_pretrained(
    config.LLM_MODEL_ID,
    trust_remote_code=True,
)

llm = AutoModelForCausalLM.from_pretrained(
    config.LLM_MODEL_ID,
    quantization_config=_bnb,
    device_map=config.LLM_DEVICE,
    trust_remote_code=True,
)
llm.eval()

if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

_vram = torch.cuda.memory_allocated(0) / 1e9 if torch.cuda.is_available() else 0
print(f"[models] LLM ready  (VRAM ≈ {_vram:.2f} GB)")
