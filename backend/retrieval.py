"""
Pinecone retrieval — embed a query with BGE-M3 then fetch top-K chunks.
"""

from pinecone import Pinecone

from . import config
from .models import embed_model

# ── Pinecone client (created once at import time) ───────────────────────────

_pc    = Pinecone(api_key=config.PINECONE_API_KEY)
_index = _pc.Index(config.PINECONE_INDEX)

print(f"[retrieval] Connected to Pinecone index '{config.PINECONE_INDEX}'")


# ── Public API ───────────────────────────────────────────────────────────────

def retrieve(query: str, top_k: int | None = None, user_email: str | None = None) -> list[dict]:
    """
    Embed *query* and return the top-K Pinecone matches.

    Each returned dict has:
        score, text_preview, notebook, section, page, source_pdf, chunk

    If *user_email* is given (or CURRENT_USER_EMAIL is set), results are
    filtered to vectors with matching ``user_email`` metadata.
    """
    k = top_k or config.TOP_K
    email = user_email or config.CURRENT_USER_EMAIL

    # BGE-M3 expects normalised embeddings for cosine; sentence-transformers
    # handles that when normalize_embeddings=True.
    vec = embed_model.encode(
        query,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).tolist()

    query_kwargs: dict = {"vector": vec, "top_k": k, "include_metadata": True}
    if email:
        query_kwargs["filter"] = {"user_email": {"$eq": email}}

    results = _index.query(**query_kwargs)

    hits: list[dict] = []
    for m in results.get("matches", []):
        meta = m.get("metadata", {})
        # Prefer the full stored text; fall back to the preview for older
        # vectors uploaded before the 'text' field was added.
        full_text = meta.get("text") or meta.get("text_preview", "")
        hits.append({
            "score":        round(m["score"], 4),
            "text":         full_text,
            "text_preview": meta.get("text_preview", full_text[:200]),
            "notebook":     meta.get("notebook", ""),
            "section":      meta.get("section", ""),
            "page":         meta.get("page", ""),
            "source_pdf":   meta.get("source_pdf", ""),
            "chunk":        meta.get("chunk", 0),
        })

    return hits
