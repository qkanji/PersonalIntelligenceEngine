"""
Phase 3 - Embed & Upload to Pinecone
=====================================
Reads every .md file produced by Phase 2, chunks the content into
fixed-size token windows, embeds each chunk with BAAI/bge-m3 (locally,
on the RTX 3050), and upserts the vectors + metadata into an existing
Pinecone index.

Usage
-----
    # One-time setup
    pip install sentence-transformers pinecone tqdm

    # Set your API key in the environment (do NOT hard-code it)
    $env:PINECONE_API_KEY = "pcsk_..."        # PowerShell
    # or
    set PINECONE_API_KEY=pcsk_...             # cmd
    # or
    export PINECONE_API_KEY=pcsk_...          # bash

    python 3_embed_upload.py
    python 3_embed_upload.py --md-dir path/to/notebooks_md
    python 3_embed_upload.py --md-dir notebooks_md --embed-batch 8 --upsert-batch 100

Configuration
-------------
All tuneable values are in the CONFIG block below or via CLI flags.

Chunking strategy
-----------------
Content is split into overlapping windows measured in *words* (a rough
but dependency-free approximation of sub-word tokens):

    CHUNK_WORDS   ≈ 512 tokens  →  380 words
    OVERLAP_WORDS ≈  64 tokens  →   50 words

Each chunk becomes one Pinecone vector.  The frontmatter fields
(notebook, section, page, order, source_pdf) are stored as metadata so
you can filter queries by notebook or section.

Vector ID
---------
    <sanitised_filename>_c<chunk_index_zero_padded>
    e.g.  Math_Notebook__Calculus__001_Derivatives_c0000
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path
from typing import Generator

from tqdm import tqdm

# ── Optional: warn early if key is missing ────────────────────────────────────
_PINECONE_KEY_ENV = "PINECONE_API_KEY"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIG  (edit here or override via CLI flags)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DEFAULT_MD_DIR       = "notebooks_md"           # folder of .md files from Phase 2
PINECONE_INDEX_NAME  = "qayim-bge-m3-index"     # must already exist in your account
MODEL_ID             = "BAAI/bge-m3"
EMBED_DEVICE         = "cuda"                   # "cpu" if no GPU available
EMBED_BATCH_SIZE     = 8                        # lower = less VRAM; 8 is safe for 6 GB
UPSERT_BATCH_SIZE    = 100                      # Pinecone max per upsert call
CHUNK_WORDS          = 380                      # ≈ 512 sub-word tokens for BGE-M3
OVERLAP_WORDS        = 50                       # ≈ 64 sub-word tokens
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    Extract YAML-style frontmatter between '---' fences.
    Returns (metadata_dict, body_text).
    Falls back gracefully if frontmatter is absent or malformed.
    """
    meta: dict = {}
    body = text

    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            fm_block = text[3:end].strip()
            body     = text[end + 4:].lstrip("\n")
            for line in fm_block.splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    meta[key.strip()] = val.strip()

    return meta, body


def sliding_window_chunks(text: str, chunk_words: int, overlap_words: int) -> list[str]:
    """
    Split *text* into overlapping word-count windows.
    Empty or whitespace-only text returns an empty list.
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    step   = max(1, chunk_words - overlap_words)
    start  = 0

    while start < len(words):
        end = min(start + chunk_words, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += step

    return chunks


def sanitize_id(s: str) -> str:
    """Replace any character that isn't alphanumeric, dash, or underscore."""
    return re.sub(r"[^A-Za-z0-9_\-]", "_", s)


def iter_batches(lst: list, n: int) -> Generator[list, None, None]:
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def fmt(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    return f"{seconds / 3600:.1f}h"


# ── Core pipeline ─────────────────────────────────────────────────────────────

def load_and_chunk_files(md_dir: Path) -> list[dict]:
    """
    Walk *md_dir*, parse every .md file, and return a list of chunk dicts:
        {
            "id":       str,          # unique Pinecone vector ID
            "text":     str,          # text to embed
            "metadata": dict,         # frontmatter + chunk info
        }
    """
    md_files = sorted(md_dir.glob("*.md"))
    if not md_files:
        print(f"[ERROR] No .md files found in: {md_dir.resolve()}")
        sys.exit(1)

    print(f"Found {len(md_files)} markdown file(s). Parsing and chunking...")
    chunks: list[dict] = []

    for md_file in tqdm(md_files, desc="Chunking", unit="file"):
        raw = md_file.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(raw)

        # Clean up LaTeX — keep it in the text so the model sees it, but
        # normalise the most extreme whitespace so tokenisation doesn't break
        body = re.sub(r"\n{3,}", "\n\n", body).strip()

        file_chunks = sliding_window_chunks(body, CHUNK_WORDS, OVERLAP_WORDS)

        if not file_chunks:
            # Empty page — still index it so there's a record
            file_chunks = [meta.get("page", md_file.stem) or "(empty page)"]

        base_id = sanitize_id(md_file.stem[:80])

        for ci, chunk_text in enumerate(file_chunks):
            chunks.append({
                "id":   f"{base_id}_c{ci:04d}",
                "text": chunk_text,
                "metadata": {
                    # Pinecone metadata values must be str / int / float / bool / list[str]
                    "notebook":   meta.get("notebook",   ""),
                    "section":    meta.get("section",    ""),
                    "page":       meta.get("page",       md_file.stem),
                    "order":      int(meta["order"]) if meta.get("order", "").isdigit() else 0,
                    "source_pdf": meta.get("source_pdf", ""),
                    "file":       md_file.name,
                    "chunk":      ci,
                    "chunks_total": len(file_chunks),
                    # Full chunk text sent to the LLM as RAG context
                    "text":        chunk_text,
                    # Short preview for the Pinecone UI / source cards
                    "text_preview": chunk_text[:200],
                },
            })

    print(f"  → {len(chunks)} chunk(s) across {len(md_files)} file(s)")
    return chunks


def embed_chunks(chunks: list[dict], device: str, batch_size: int) -> list[dict]:
    """
    Add an "embedding" key to every chunk dict, then return the list.
    Uses sentence-transformers with normalize_embeddings=True (cosine ready).
    """
    # Import here so the rest of the script can run for --help without torch
    from sentence_transformers import SentenceTransformer

    print(f"\nLoading {MODEL_ID} on {device}...")
    model = SentenceTransformer(MODEL_ID, device=device)
    print(f"  Embedding dimension: {model.get_sentence_embedding_dimension()}")

    texts  = [c["text"] for c in chunks]
    total  = len(texts)
    t0     = time.time()

    all_embeddings = []
    for i, batch in enumerate(tqdm(
        list(iter_batches(texts, batch_size)),
        desc="Embedding",
        unit="batch",
    )):
        embs = model.encode(
            batch,
            batch_size=batch_size,
            normalize_embeddings=True,   # L2-normalise for cosine similarity
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        all_embeddings.extend(embs.tolist())

        done = min((i + 1) * batch_size, total)
        elapsed = time.time() - t0
        rate    = done / elapsed
        eta     = (total - done) / rate if rate > 0 else 0
        tqdm.write(f"  {done}/{total} chunks  ({rate:.1f} chunks/s, ETA {fmt(eta)})")

    for chunk, emb in zip(chunks, all_embeddings):
        chunk["embedding"] = emb

    print(f"Embedding complete in {fmt(time.time() - t0)}.")
    return chunks


def upload_to_pinecone(chunks: list[dict], index_name: str, api_key: str, upsert_batch: int):
    """
    Upsert all chunks into the named Pinecone index.
    """
    from pinecone import Pinecone                        # pinecone>=3.0

    print(f"\nConnecting to Pinecone index '{index_name}'...")
    pc    = Pinecone(api_key=api_key)
    index = pc.Index(index_name)

    stats = index.describe_index_stats()
    print(f"  Index dimension : {stats.get('dimension', 'unknown')}")
    print(f"  Vectors before  : {stats.get('total_vector_count', 'unknown')}")

    vectors = [
        {
            "id":       c["id"],
            "values":   c["embedding"],
            "metadata": c["metadata"],
        }
        for c in chunks
    ]

    t0         = time.time()
    total      = len(vectors)
    upserted   = 0

    for batch in tqdm(
        list(iter_batches(vectors, upsert_batch)),
        desc="Upserting",
        unit="batch",
    ):
        index.upsert(vectors=batch)
        upserted += len(batch)

    elapsed = time.time() - t0
    stats2  = index.describe_index_stats()
    print(f"\nUpload complete in {fmt(elapsed)}.")
    print(f"  Vectors upserted : {upserted}")
    print(f"  Vectors in index : {stats2.get('total_vector_count', 'unknown')}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Embed markdown pages with BGE-M3 and upload to Pinecone."
    )
    parser.add_argument(
        "--md-dir",
        default=DEFAULT_MD_DIR,
        help=f"Folder containing .md files (default: {DEFAULT_MD_DIR})",
    )
    parser.add_argument(
        "--embed-batch",
        type=int,
        default=EMBED_BATCH_SIZE,
        help=f"Sentences per GPU batch (default: {EMBED_BATCH_SIZE}; lower to save VRAM)",
    )
    parser.add_argument(
        "--upsert-batch",
        type=int,
        default=UPSERT_BATCH_SIZE,
        help=f"Vectors per Pinecone upsert call (default: {UPSERT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--device",
        default=EMBED_DEVICE,
        help="Torch device for embedding (default: cuda)",
    )
    args = parser.parse_args()

    # ── API key ──────────────────────────────────────────────────────────────
    api_key = os.environ.get(_PINECONE_KEY_ENV, "").strip()
    if not api_key:
        print(
            f"[ERROR] Pinecone API key not found.\n"
            f"Set it with:  $env:{_PINECONE_KEY_ENV} = 'your-key'   (PowerShell)\n"
            f"          or: set {_PINECONE_KEY_ENV}=your-key         (cmd)\n"
            f"          or: export {_PINECONE_KEY_ENV}=your-key      (bash)"
        )
        sys.exit(1)

    # ── Paths ────────────────────────────────────────────────────────────────
    md_dir = Path(args.md_dir)
    if not md_dir.is_dir():
        print(f"[ERROR] Not a directory: {md_dir.resolve()}")
        sys.exit(1)

    print("=" * 60)
    print("Phase 3: Embed + Upload")
    print(f"  Source dir     : {md_dir.resolve()}")
    print(f"  Model          : {MODEL_ID}")
    print(f"  Device         : {args.device}")
    print(f"  Embed batch    : {args.embed_batch}")
    print(f"  Chunk size     : ~{CHUNK_WORDS} words / {OVERLAP_WORDS} word overlap")
    print(f"  Pinecone index : {PINECONE_INDEX_NAME}")
    print("=" * 60)

    overall = time.time()

    chunks  = load_and_chunk_files(md_dir)
    chunks  = embed_chunks(chunks, device=args.device, batch_size=args.embed_batch)
    upload_to_pinecone(chunks, PINECONE_INDEX_NAME, api_key, args.upsert_batch)

    print(f"\n✅ Done in {fmt(time.time() - overall)}.")


if __name__ == "__main__":
    main()
