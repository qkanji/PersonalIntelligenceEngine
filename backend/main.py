"""
FastAPI application — POST /api/chat/stream (SSE) + GET /api/health
"""

from __future__ import annotations

import json
from typing import Generator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import config
from .retrieval import retrieve
from .chat import build_messages, stream_tokens

# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="Personal Intelligence Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_ORIGIN, "http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ──────────────────────────────────────────────────────────────────

class Turn(BaseModel):
    role: str       # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[Turn] = []


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    from .models import EMBED_DIM
    import torch

    vram = torch.cuda.memory_allocated(0) / 1e9 if torch.cuda.is_available() else 0
    return {
        "status": "ok",
        "embed_model": config.EMBED_MODEL_ID,
        "embed_dim": EMBED_DIM,
        "llm_model": config.LLM_MODEL_ID,
        "llm_vram_gb": round(vram, 2),
        "pinecone_index": config.PINECONE_INDEX,
        "top_k": config.TOP_K,
    }


# ── Chat (SSE stream) ───────────────────────────────────────────────────────

def _sse_generator(req: ChatRequest) -> Generator[str, None, None]:
    """
    1. Retrieve top-K chunks from Pinecone
    2. Build RAG prompt
    3. Stream LLM tokens as SSE `data:` lines
    4. Send a final `[SOURCES]` event with the retrieval metadata
    """
    # 1. Retrieve
    chunks = retrieve(req.message)

    # 2. Build prompt
    history = [{"role": t.role, "content": t.content} for t in req.history]
    messages = build_messages(req.message, chunks, history)

    # 3. Stream tokens
    for token in stream_tokens(messages):
        # SSE format: "data: <payload>\n\n"
        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

    # 4. Sources
    yield f"data: {json.dumps({'type': 'sources', 'content': chunks})}\n\n"

    # 5. Done signal
    yield "data: [DONE]\n\n"


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    return StreamingResponse(
        _sse_generator(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",      # nginx / reverse-proxy hint
        },
    )
