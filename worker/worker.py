#!/usr/bin/env python3
"""
RunPod GPU Worker — OCR + Embed + Upload
=========================================
Runs inside a RunPod 4090 spot container.  The entire body is wrapped in
try/finally so the pod **always** self-terminates on exit (success or crash).

Pipeline
--------
1. Authenticate with GCS using the injected service-account key.
2. Download structure.json for the user to discover page folders.
3. For each page folder, download PNGs from GCS.
4. Run Qwen3.5-9B (FP8, vLLM offline) to OCR every page.
5. Upload resulting .md files to GCS as checkpoints.
6. After OCR is done, free VRAM and load BGE-M3.
7. Chunk all markdown, embed with BGE-M3, upsert to Pinecone.
8. Write done.json to GCS.
9. Self-terminate via RunPod API.

Environment variables (set by the orchestrator)
-----------------------------------------------
USER_EMAIL          — GCS folder prefix / Pinecone metadata
GCS_BUCKET          — bucket name
PINECONE_API_KEY    — Pinecone API key
PINECONE_INDEX      — Pinecone index name
RUNPOD_API_KEY      — for self-termination
GCP_SA_KEY_JSON_B64 — base64-encoded GCP service-account JSON
RUNPOD_POD_ID       — injected automatically by RunPod runtime
"""

import asyncio
import base64
import gc
import json
import os
import re
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import requests
from gcloud.aio.storage import Storage

print("[worker] imports OK", flush=True)

# ── Config from environment ──────────────────────────────────────────────────

USER_EMAIL       = os.environ["USER_EMAIL"]
GCS_BUCKET       = os.environ.get("GCS_BUCKET", "pie-data")
PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]
PINECONE_INDEX   = os.environ.get("PINECONE_INDEX", "qayim-bge-m3-index")
RUNPOD_API_KEY   = os.environ.get("RUNPOD_API_KEY", "")
POD_ID           = os.environ.get("RUNPOD_POD_ID", "")

# vLLM settings
MODEL_ID         = "lovedheart/Qwen3.5-9B-FP8"
GPU_UTIL         = 0.90
MAX_MODEL_LEN    = 40960
MAX_IMAGES_PER_PROMPT = 75

# Embedding / chunking
EMBED_MODEL_ID   = "BAAI/bge-m3"
CHUNK_WORDS      = 380
OVERLAP_WORDS    = 50
EMBED_BATCH      = 32
UPSERT_BATCH     = 100

# Working directory
WORK_DIR = Path(tempfile.mkdtemp(prefix="rag_worker_"))


# ── Self-termination ─────────────────────────────────────────────────────────

def terminate_self():
    """Terminate this RunPod pod via the REST API."""
    if not RUNPOD_API_KEY or not POD_ID:
        print("[worker] No RUNPOD_API_KEY or POD_ID — skipping self-terminate")
        return
    try:
        resp = requests.delete(
            f"https://rest.runpod.io/v1/pods/{POD_ID}",
            headers={
                "Authorization": f"Bearer {RUNPOD_API_KEY}",
            },
            timeout=15,
        )
        print(f"[worker] Self-terminate response: {resp.status_code}")
    except Exception as e:
        print(f"[worker] Self-terminate failed: {e}")


# ── GCS helpers ──────────────────────────────────────────────────────────────

def setup_gcs_auth():
    """Write SA key JSON to disk and set the env var."""
    global _gcs_client
    b64 = os.environ.get("GCP_SA_KEY_JSON_B64", "")
    if not b64:
        print("[worker] No GCP_SA_KEY_JSON_B64, relying on default credentials")
        return
    key_path = WORK_DIR / "sa_key.json"
    key_path.write_bytes(base64.b64decode(b64))
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(key_path)
    _gcs_client = None  # force re-init with the new credentials
    print(f"[worker] GCS auth configured → {key_path}")


_gcs_client: "storage.Client | None" = None

def gcs_client():
    global _gcs_client
    if _gcs_client is None:
        from google.cloud import storage
        _gcs_client = storage.Client()
    return _gcs_client


def download_blob_to_file(bucket_name: str, blob_name: str, local_path: Path):
    client = gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    blob.download_to_filename(str(local_path))


def upload_string_to_gcs(bucket_name: str, blob_name: str, data: str, content_type="text/markdown"):
    client = gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(data, content_type=content_type)


def list_blobs_with_prefix(bucket_name: str, prefix: str) -> list[str]:
    client = gcs_client()
    blobs = client.list_blobs(bucket_name, prefix=prefix)
    return [b.name for b in blobs]


# ── OCR helpers ──────────────────────────────────────────────────────────────

def build_ocr_prompt(image_paths: list[Path], processor) -> dict:
    """
    Build a vLLM-compatible prompt dict for multi-image OCR securely via processor.
    Returns {"prompt": str, "multi_modal_data": {"image": [PIL.Image, ...]}}.
    """
    from PIL import Image

    images = [Image.open(p).convert("RGB") for p in sorted(image_paths)]
    n = len(images)

    # Standard OpenAI messages format
    messages = [
        {
            "role": "system",
            "content": (
                "You are an OCR assistant. Convert the document images into clean Markdown. "
                "Preserve headings, lists, tables, and math (use LaTeX $...$ and $$...$$). "
                "CRITICAL: Do not use unicode box-drawing characters; represent trees/diagrams as standard nested markdown lists. "
                "Never use unicode subscripts/superscripts; always use LaTeX for chemical formulas and math. "
                "Output ONLY the Markdown, no commentary."
            )
        },
        {
            "role": "user",
            "content": [
                *[{"type": "image", "image": img} for img in images],
                {"type": "text", "text": f"Convert these {n} page image(s) into Markdown."}
            ]
        }
    ]

    prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    return {"prompt": prompt, "multi_modal_data": {"image": images}}


async def process_image(
    img_path: Path, 
    processor, 
    engine, 
    sampling_params, 
    image_semaphore: asyncio.Semaphore
) -> str:
    """Process a single image concurrently via AsyncLLMEngine."""
    async with image_semaphore:
        # Build prompt securely. This loads the image into memory via PIL (offloaded to thread).
        prompt_data = await asyncio.to_thread(build_ocr_prompt, [img_path], processor)
        
        request_id = str(uuid.uuid4())
        results_generator = engine.generate(
            prompt_data,
            sampling_params,
            request_id,
        )
        
        final_output = None
        async for request_output in results_generator:
            final_output = request_output
            
        text = final_output.outputs[0].text.strip()
        
        # Remove reasoning chains (like DeepSeek R1 or Qwen reasoning variants use)
        if "</think>" in text:
            text = text.split("</think>")[-1].strip()
            
        return text


async def process_page(
    page: dict,
    structure: dict,
    images_root: Path,
    storage: Storage,
    processor,
    engine,
    sampling_params,
    page_semaphore: asyncio.Semaphore,
    image_semaphore: asyncio.Semaphore,
    progress_state: dict
) -> dict | None:
    """Process all images for a given page sequentially, then upload."""
    async with page_semaphore:
        gcs_folder = page.get("gcs_folder", "")
        num_images = page.get("num_images", 1)
        page_name = page["name"]
        
        unique_id = f"{sanitize_id(page.get('section', ''))}_{page.get('order', 0):03d}_{sanitize_id(page_name)}"
        
        # Download images for this page sequentially or via aio (we do via aio concurrently)
        page_dir = images_root / unique_id
        page_dir.mkdir(parents=True, exist_ok=True)
        
        async def dl_image(idx: int):
            img_blob = f"{gcs_folder}/p{idx:04d}.png"
            local_img = page_dir / f"p{idx:04d}.png"
            if not local_img.exists():
                try:
                    res = await storage.download(GCS_BUCKET, img_blob)
                    local_img.write_bytes(res)
                except Exception as e:
                    print(f"  ⚠ Failed to download {img_blob}: {e}")
            return local_img
            
        download_tasks = [dl_image(i) for i in range(1, num_images + 1)]
        await asyncio.gather(*download_tasks)
        
        image_files = sorted(page_dir.glob("*.png"))
        if not image_files:
            print(f"  ⚠ No images for: {page_name}")
            return None
            
        # Process every image on this page concurrently
        image_tasks = [
            process_image(p, processor, engine, sampling_params, image_semaphore)
            for p in image_files
        ]
        
        # gather preserves the order of task creation, ensuring stitched text is sequentially correct
        image_texts = await asyncio.gather(*image_tasks)
        
        # Concatenate markdown
        full_markdown = "\n\n".join(image_texts).strip()
        
        # Prepend frontmatter
        notebook = structure.get("notebook", "")
        frontmatter = (
            f"---\n"
            f"notebook: {notebook}\n"
            f"section: {page.get('section', '')}\n"
            f"path: {page.get('path', '')}\n"
            f"page: {page_name}\n"
            f"order: {page.get('order', 0)}\n"
            f"source_pdf: {page_name}\n"
            f"---\n\n"
        )
        full_md = frontmatter + full_markdown
        
        # Checkpoint: upload .md to GCS immediately over async as strict utf-8 bytes
        md_blob = f"{USER_EMAIL}/output_md/{unique_id}.md"
        await storage.upload(GCS_BUCKET, md_blob, full_md.encode("utf-8"), content_type="text/markdown")
        
        progress_state["completed"] += 1
        comp = progress_state["completed"]
        tot = progress_state["total"]
        elapsed = time.time() - progress_state["start_time"]
        eta_secs = (elapsed / comp) * (tot - comp) if comp > 0 else 0
        
        def fmt_t(s):
            if s < 60: return f"{s:.0f}s"
            if s < 3600: return f"{s/60:.1f}m"
            return f"{s/3600:.1f}h"
            
        print(f"  ✅ {page_name} → {len(full_markdown)} chars | {comp}/{tot} pages (ETA: {fmt_t(eta_secs)})")
        
        return {
            "name": page_name,
            "section": page.get("section", ""),
            "order": page.get("order", 0),
            "markdown": full_md,
        }


async def run_ocr_async(structures: list[dict], images_root: Path) -> list[dict]:
    """
    Setup Async vLLM Engine and process all pages asynchronously.
    """
    from vllm.engine.arg_utils import AsyncEngineArgs
    from vllm.engine.async_llm_engine import AsyncLLMEngine
    from vllm import SamplingParams
    from transformers import AutoProcessor

    print(f"[worker] Loading processor for chat templating...")
    processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)

    print(f"[worker] Initializing Async vLLM Engine: {MODEL_ID} (8-bit)")
    engine_args = AsyncEngineArgs(
        model=MODEL_ID,
        dtype="float16",
        quantization="fp8",
        gpu_memory_utilization=GPU_UTIL,
        max_model_len=MAX_MODEL_LEN,
        limit_mm_per_prompt={"image": MAX_IMAGES_PER_PROMPT},
        trust_remote_code=True,
        enable_prefix_caching=True,
    )
    engine = AsyncLLMEngine.from_engine_args(engine_args)
    # Increase max_tokens so reasoning models have enough runway to think AND output the final markdown without getting cut off
    sampling = SamplingParams(temperature=0.0, max_tokens=8192)

    # Throttling
    page_semaphore = asyncio.Semaphore(5)    # Max concurrent pages
    image_semaphore = asyncio.Semaphore(150) # Peak Host RAM cap for loaded PIL images
    
    # Build "resume" set — skip pages whose .md already exists in GCS
    existing_md = set(list_blobs_with_prefix(
        GCS_BUCKET,
        f"{USER_EMAIL}/output_md/",
    ))

    # Iterate over all structure groupings and enqueue pending pages
    all_page_tasks = []
    
    progress_state = {"completed": 0, "total": 0, "start_time": time.time()}
    
    # Use gcloud-aio Storage context manager for efficient connection pooling
    async with aiohttp.ClientSession() as session:
        async with Storage(session=session) as storage:
            for structure in structures:
                notebook_name = structure.get("notebook", "unknown")
                pages = structure.get("pages", [])
                
                pending = []
                for page in pages:
                    unique_id = f"{sanitize_id(page.get('section', ''))}_{page.get('order', 0):03d}_{sanitize_id(page['name'])}"
                    md_blob = f"{USER_EMAIL}/output_md/{unique_id}.md"
                    if md_blob in existing_md:
                        print(f"  ⏩ Skipping (already done): {page['name']}")
                        continue
                    pending.append(page)
                    
                print(f"[worker] {notebook_name}: Enqueueing {len(pending)} pending pages.")
                
                for page in pending:
                    progress_state["total"] += 1
                    task = asyncio.create_task(
                        process_page(
                            page, structure, images_root, storage, 
                            processor, engine, sampling, 
                            page_semaphore, image_semaphore,
                            progress_state
                        )
                    )
                    all_page_tasks.append(task)
            
            # Fire all scheduled tasks simultaneously
            print(f"[worker] Gathering {len(all_page_tasks)} page pipelines...")
            raw_results = await asyncio.gather(*all_page_tasks)
            
    # Free VRAM fully
    import torch
    
    if hasattr(engine, 'shutdown_background_loop'):
        engine.shutdown_background_loop()
    
    del engine
    del processor
    gc.collect()
    torch.cuda.empty_cache()
    
    try:
        from vllm.distributed.parallel_state import destroy_model_parallel
        destroy_model_parallel()
    except Exception:
        pass
    
    print("[worker] vLLM async model unloaded, VRAM freed")

    # Filter out None results
    return [r for r in raw_results if r]


# ── Embedding helpers ────────────────────────────────────────────────────────

def sanitize_id(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]", "_", s)[:80]


def sliding_window_chunks(text: str, chunk_words: int, overlap_words: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks = []
    step = max(1, chunk_words - overlap_words)
    start = 0
    while start < len(words):
        end = min(start + chunk_words, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += step
    return chunks


def parse_frontmatter(text: str) -> tuple[dict, str]:
    meta: dict = {}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            fm_block = text[3:end].strip()
            body = text[end + 4:].lstrip("\n")
            for line in fm_block.splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    meta[key.strip()] = val.strip()
    return meta, body


def embed_and_upload(md_results: list[dict]):
    """
    Chunk all markdown, embed with BGE-M3, upsert to Pinecone.
    """
    from sentence_transformers import SentenceTransformer
    from pinecone import Pinecone

    print(f"[worker] Loading embedding model: {EMBED_MODEL_ID}")
    model = SentenceTransformer(EMBED_MODEL_ID, device="cuda")

    # Build chunks
    all_chunks: list[dict] = []
    for result in md_results:
        meta, body = parse_frontmatter(result["markdown"])
        body = re.sub(r"\n{3,}", "\n\n", body).strip()

        page_chunks = sliding_window_chunks(body, CHUNK_WORDS, OVERLAP_WORDS)
        if not page_chunks:
            page_chunks = [meta.get("page", result["name"]) or "(empty page)"]

        base_id = sanitize_id(result["name"])
        for ci, chunk_text in enumerate(page_chunks):
            all_chunks.append({
                "id": f"{base_id}_c{ci:04d}",
                "text": chunk_text,
                "metadata": {
                    "notebook":     meta.get("notebook", ""),
                    "section":      meta.get("section", result.get("section", "")),
                    "page":         meta.get("page", result["name"]),
                    "order":        int(meta["order"]) if meta.get("order", "").isdigit() else result.get("order", 0),
                    "source_pdf":   meta.get("source_pdf", ""),
                    "chunk":        ci,
                    "chunks_total": len(page_chunks),
                    "text":         chunk_text,
                    "text_preview": chunk_text[:200],
                    "user_email":   USER_EMAIL,
                },
            })

    print(f"[worker] {len(all_chunks)} chunks from {len(md_results)} pages")

    if not all_chunks:
        print("[worker] Nothing to embed — skipping")
        return

    # Embed in batches
    print("[worker] Embedding chunks...")
    texts = [c["text"] for c in all_chunks]
    all_embeddings = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch_texts = texts[i : i + EMBED_BATCH]
        emb = model.encode(batch_texts, normalize_embeddings=True, convert_to_numpy=True)
        all_embeddings.extend(emb.tolist())
        print(f"  Embedded {min(i + EMBED_BATCH, len(texts))}/{len(texts)}")

    # Free embedding model
    import torch
    del model
    gc.collect()
    torch.cuda.empty_cache()

    # Upsert to Pinecone
    print("[worker] Upserting to Pinecone...")
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(PINECONE_INDEX)

    for i in range(0, len(all_chunks), UPSERT_BATCH):
        batch = all_chunks[i : i + UPSERT_BATCH]
        batch_emb = all_embeddings[i : i + UPSERT_BATCH]
        vectors = [
            {"id": c["id"], "values": e, "metadata": c["metadata"]}
            for c, e in zip(batch, batch_emb)
        ]
        index.upsert(vectors=vectors)  # type: ignore[arg-type]
        print(f"  Upserted {min(i + UPSERT_BATCH, len(all_chunks))}/{len(all_chunks)}")

    print(f"[worker] ✅ {len(all_chunks)} vectors upserted to Pinecone")


# ── Main pipeline ────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    print("=" * 60)
    print(f"[worker] Starting OCR + Embed pipeline")
    print(f"  User:   {USER_EMAIL}")
    print(f"  Bucket: {GCS_BUCKET}")
    print(f"  Model:  {MODEL_ID}")
    print(f"  Pod:    {POD_ID or '(local)'}")
    print("=" * 60)

    # 1. Setup GCS auth
    setup_gcs_auth()

    # 2. Find structure files for this user
    prefix = f"{USER_EMAIL}/input_images/"
    all_blobs = list_blobs_with_prefix(GCS_BUCKET, prefix)

    # Find structure.json files
    structure_blobs = [b for b in all_blobs if b.endswith("structure.json")]
    if not structure_blobs:
        print(f"[worker] No structure.json found under {prefix}")
        return

    all_results: list[dict] = []
    images_root = WORK_DIR / "images"
    images_root.mkdir(exist_ok=True)

    structure_data_list = []
    for struct_blob in structure_blobs:
        # Download structure.json
        local_struct = WORK_DIR / f"structure_{uuid.uuid4().hex[:8]}.json"
        download_blob_to_file(GCS_BUCKET, struct_blob, local_struct)

        with open(local_struct, "r", encoding="utf-8") as f:
            structure_data_list.append(json.load(f))

    # 3. OCR all pages asynchronously via continuous batching
    if structure_data_list:
        results = asyncio.run(run_ocr_async(structure_data_list, images_root))
        all_results.extend(results)

    # 4. Also pick up any .md files from resumed/prior runs
    existing_md_blobs = list_blobs_with_prefix(GCS_BUCKET, f"{USER_EMAIL}/output_md/")
    # Download any .md we didn't just produce (from prior incomplete runs)
    produced_names = {sanitize_id(r["name"]) for r in all_results}
    for md_blob in existing_md_blobs:
        blob_stem = md_blob.rsplit("/", 1)[-1].replace(".md", "")
        if blob_stem not in produced_names:
            local_md = WORK_DIR / "resumed" / f"{blob_stem}.md"
            download_blob_to_file(GCS_BUCKET, md_blob, local_md)
            md_text = local_md.read_text(encoding="utf-8")
            meta, _ = parse_frontmatter(md_text)
            all_results.append({
                "name": meta.get("page", blob_stem),
                "section": meta.get("section", ""),
                "order": int(meta["order"]) if meta.get("order", "").isdigit() else 0,
                "markdown": md_text,
            })

    # 5. Embed and upload to Pinecone
    if all_results:
        embed_and_upload(all_results)
    else:
        print("[worker] No markdown to embed")

    # 6. Write done.json
    done = json.dumps({
        "status": "completed",
        "user_email": USER_EMAIL,
        "pages_processed": len(all_results),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    upload_string_to_gcs(GCS_BUCKET, f"{USER_EMAIL}/done.json", done, "application/json")
    print(f"\n[worker] done.json written to GCS")

    elapsed = time.time() - t0
    minutes = elapsed / 60
    print(f"[worker] ✅ Pipeline complete in {minutes:.1f} minutes")


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[worker] ❌ FATAL ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
    finally:
        print("[worker] Self-terminating pod...")
#         terminate_self()
        while True:
            pass