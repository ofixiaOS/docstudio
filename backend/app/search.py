"""Hybrid lexical + vector search over sources and memories."""

from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from .ai import ai
from .settings import get_gemini_api_key, settings
from .storage import Store


def index_source_embeddings(source_id: str, store: Store) -> int:
    """Compute and persist Gemini embeddings for any un-embedded chunks of *source_id*."""
    if not get_gemini_api_key():
        return 0
    chunks = store.get_source_chunks(source_id)
    pending = [item for item in chunks if not item.get("embedding_json")]
    if not pending:
        return 0
    vectors = ai.embed_documents(
        [item["content"] for item in pending],
        [item["filename"] for item in pending],
    )
    pairs = [(item["id"], vector) for item, vector in zip(pending, vectors) if vector]
    store.set_chunk_embeddings(pairs, settings.embedding_model)
    return len(pairs)


async def hybrid_source_search(project_id: str, query: str, limit: int, store: Store) -> list[dict]:
    """RRF-fused lexical + vector search over project source chunks."""
    lexical = store.search_sources(project_id, query, limit)
    vector: list[dict] = []
    if get_gemini_api_key():
        try:
            query_embedding = await run_in_threadpool(ai.embed_query, query)
            vector = store.search_sources_vector(project_id, query_embedding, limit)
        except Exception:
            vector = []
    scores: dict[str, float] = {}
    values: dict[str, dict] = {}
    for result_set, weight in ((lexical, 1.0), (vector, 1.25)):
        for rank, item in enumerate(result_set, start=1):
            values[item["id"]] = item
            scores[item["id"]] = scores.get(item["id"], 0) + weight / (40 + rank)
    ordered = sorted(values.values(), key=lambda item: scores[item["id"]], reverse=True)
    return ordered[:limit]


async def hybrid_memory_search(project_id: str, query: str, limit: int, store: Store) -> list[dict]:
    """RRF-fused lexical + vector search over project memories."""
    lexical = store.search_memories(project_id, query, limit)
    vector: list[dict] = []
    if get_gemini_api_key():
        try:
            query_embedding = await run_in_threadpool(ai.embed_query, query)
            vector = store.search_memories_vector(project_id, query_embedding, limit)
        except Exception:
            vector = []
    scores: dict[str, float] = {}
    values: dict[str, dict] = {}
    for result_set, weight in ((lexical, 1.0), (vector, 1.25)):
        for rank, item in enumerate(result_set, start=1):
            values[item["id"]] = item
            importance_boost = float(item.get("importance", 0.5)) * 0.15
            scores[item["id"]] = scores.get(item["id"], 0) + (weight / (40 + rank)) + importance_boost
    ordered = sorted(values.values(), key=lambda item: scores[item["id"]], reverse=True)
    return ordered[:limit]
