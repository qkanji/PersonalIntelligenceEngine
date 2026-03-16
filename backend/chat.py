"""
RAG prompt builder + streaming token generator.
"""

from __future__ import annotations

import threading
from typing import Generator

import torch
from transformers import TextIteratorStreamer

from . import config
from .models import llm, tokenizer

# ── System prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are a helpful study assistant for a high-school student. "
    "You have access to excerpts from the student's personal class notes, "
    "provided as numbered [Source N] blocks below each question. "
    "Rules you must follow:\n"
    "1. Base your answer ONLY on the provided sources. "
    "Do NOT speculate or invent details that are not present in the sources.\n"
    "2. If the answer is not in the sources, say exactly: "
    "'I couldn't find that in your notes.' — do not guess.\n"
    "3. Cite every claim with [Source N].\n"
    "4. Use Markdown formatting.\n"
    "5. Write all mathematics in LaTeX: inline as $...$ and display as $$...$$."
)

# ── Prompt builder ───────────────────────────────────────────────────────────


def build_messages(
    user_message: str,
    chunks: list[dict],
    history: list[dict] | None = None,
) -> list[dict]:
    """
    Assemble the chat-template message list for the LLM.

    Parameters
    ----------
    user_message : latest user question
    chunks       : list of retrieval dicts (from retrieval.retrieve)
    history      : prior turns as [{"role": "user"|"assistant", "content": ...}, ...]
    """
    context_block = "\n\n".join(
        f"[Source {i + 1}] (notebook: {c['notebook']}, section: {c['section']}, page: {c['page']})\n{c['text']}"
        for i, c in enumerate(chunks)
    )

    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    if history:
        messages.extend(history)

    # Inject context into the latest user turn so the model sees it
    augmented = (
        f"### Retrieved context\n{context_block}\n\n"
        f"### Question\n{user_message}"
    )
    messages.append({"role": "user", "content": augmented})

    return messages


# ── Streaming generator ──────────────────────────────────────────────────────


def stream_tokens(messages: list[dict]) -> Generator[str, None, None]:
    """
    Tokenise *messages* with the chat template, run model.generate() in a
    background thread, and yield decoded token strings as they appear.
    """
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
    )
    inputs = tokenizer(text, return_tensors="pt").to(llm.device)

    streamer = TextIteratorStreamer(
        tokenizer,
        skip_prompt=True,
        skip_special_tokens=True,
    )

    gen_kwargs = dict(
        **inputs,
        max_new_tokens=config.MAX_NEW_TOKENS,
        do_sample=True,
        temperature=0.6,
        top_p=0.9,
        streamer=streamer,
    )

    thread = threading.Thread(target=llm.generate, kwargs=gen_kwargs, daemon=True)
    thread.start()

    for token_text in streamer:
        yield token_text

    thread.join()
