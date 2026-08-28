"""Retrieval against Pinecone — hybrid (dense+sparse), optional multi-query fusion, optional
hosted reranking. See specs/02-advanced-retrieval.md for the design and specs/06-phased-rollout.md
for what's flag-gated vs. always-on (hybrid is always on; multi-query and rerank are config flags).
"""
from __future__ import annotations

from rag import config
from rag.ingestion.indexing import embed_dense, embed_sparse, get_pinecone_client


def _hybrid_score_norm(dense: list[float], sparse: dict, alpha: float) -> tuple[list[float], dict]:
    """Scales the QUERY-side dense/sparse vectors so a single index.query() call with both
    produces the desired alpha-weighted blend. This is Pinecone's own documented pattern —
    verified live against their hybrid search guide, not assumed: alpha scales the query vectors
    before the call, it does not blend two separate result sets afterward."""
    if not 0 <= alpha <= 1:
        raise ValueError("alpha must be between 0 and 1")
    hdense = [v * alpha for v in dense]
    hsparse = {"indices": sparse["indices"], "values": [v * (1 - alpha) for v in sparse["values"]]}
    return hdense, hsparse


def _query_index(video_id: str, question: str, top_k: int) -> list[dict]:
    pc = get_pinecone_client()
    index = pc.Index(config.PINECONE_INDEX_NAME)
    [dense] = embed_dense([question], input_type="query")
    [sparse] = embed_sparse([question], input_type="query")
    hdense, hsparse = _hybrid_score_norm(dense, sparse, config.HYBRID_ALPHA)
    result = index.query(
        namespace=video_id,
        vector=hdense,
        sparse_vector=hsparse,
        top_k=top_k,
        include_metadata=True,
    )
    return [
        {
            "id": match["id"],
            "text": match["metadata"]["text"],
            "score": match["score"],
            "start_ms": match["metadata"].get("start_ms", 0),
        }
        for match in result["matches"]
    ]


def _reciprocal_rank_fusion(result_lists: list[list[dict]], k: int = 60) -> list[dict]:
    """Combines several ranked result lists (one per query variant, from multi-query expansion)
    into one, using each chunk's *rank position* rather than its raw score — scores from separate
    query calls aren't directly comparable, ranks are. Standard RAG-Fusion technique."""
    rrf_scores: dict[str, float] = {}
    chunks_by_id: dict[str, dict] = {}
    for results in result_lists:
        for rank, chunk in enumerate(results):
            rrf_scores[chunk["id"]] = rrf_scores.get(chunk["id"], 0) + 1 / (k + rank + 1)
            chunks_by_id.setdefault(chunk["id"], chunk)
    ordered_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)
    return [chunks_by_id[cid] for cid in ordered_ids]


def _rerank(question: str, chunks: list[dict], top_n: int) -> list[dict]:
    """Best-effort: if the hosted rerank call fails (quota exhausted, transient error), fall back
    to the pre-rerank ordering rather than breaking the whole answer over a ranking nicety."""
    if not chunks:
        return chunks
    try:
        pc = get_pinecone_client()
        result = pc.inference.rerank(
            model=config.RERANK_MODEL,
            query=question,
            documents=[{"id": c["id"], "chunk_text": c["text"]} for c in chunks],
            top_n=min(top_n, len(chunks)),
            rank_fields=["chunk_text"],
        )
        return [{**chunks[item.index], "score": item.score} for item in result.data]
    except Exception:
        return chunks[:top_n]


def retrieve(video_id: str, question: str, query_variants: list[str] | None = None) -> list[dict]:
    """Main entry point. `query_variants` (optional) are extra paraphrases from multi-query
    expansion — when given, every variant (plus the original question) is queried independently
    and the results fused via reciprocal rank fusion before reranking/trimming to TOP_K."""
    queries = [question, *(query_variants or [])]
    result_lists = [_query_index(video_id, q, config.RETRIEVE_K) for q in queries]
    chunks = result_lists[0] if len(result_lists) == 1 else _reciprocal_rank_fusion(result_lists)

    if config.RERANK_ENABLED:
        return _rerank(question, chunks, config.TOP_K)
    return chunks[: config.TOP_K]


def format_context(chunks: list[dict]) -> str:
    return "\n\n".join(c["text"] for c in chunks)
