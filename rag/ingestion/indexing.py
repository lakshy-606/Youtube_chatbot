"""Chunk a transcript, embed it via Pinecone Inference, and upsert into the video's namespace.

See specs/02-advanced-retrieval.md for why embeddings run through Pinecone Inference rather than
a separate provider, and why video_id is used as the Pinecone namespace. `ensure_video_indexed`
is the "don't re-embed on every question" persistence win a FAISS-on-disk cache would have given
in a traditional server — achieved here through Pinecone itself, since a stateless Vercel function
can't rely on local disk surviving between invocations.
"""
from __future__ import annotations

from langchain_groq import ChatGroq
from pinecone import Pinecone, ServerlessSpec

from rag import config

_EMBED_BATCH_SIZE = 96  # conservative batch size for Pinecone Inference embed calls
_UPSERT_BATCH_SIZE = 96

_pc: Pinecone | None = None


def get_pinecone_client() -> Pinecone:
    global _pc
    if _pc is None:
        _pc = Pinecone(api_key=config.PINECONE_API_KEY)
    return _pc


def ensure_index():
    """Create the shared index if it doesn't exist yet, and return a handle to it."""
    pc = get_pinecone_client()
    if not pc.has_index(config.PINECONE_INDEX_NAME):
        pc.create_index(
            name=config.PINECONE_INDEX_NAME,
            vector_type="dense",
            dimension=config.EMBED_DIMENSION,
            metric="dotproduct",
            spec=ServerlessSpec(cloud=config.PINECONE_CLOUD, region=config.PINECONE_REGION),
        )
    return pc.Index(config.PINECONE_INDEX_NAME)


_SCHEMA_SENTINEL_FIELDS = ("start_ms", "topic")  # bump/extend when the metadata schema next changes


def _sample_vector(index, video_id: str):
    result = index.fetch(ids=[f"{video_id}-0"], namespace=video_id)
    return (result.vectors or {}).get(f"{video_id}-0")


def namespace_has_vectors(index, video_id: str) -> bool:
    """True only if the namespace exists AND its vectors match the current schema.

    A namespace indexed before a metadata field or vector component was added (e.g. `start_ms`
    for timestamp citations, `sparse_values` for Phase 4 hybrid search, `topic` for Phase 5
    guardrails) would otherwise look "already indexed" forever and silently keep serving stale/
    incomplete data — exactly the bug that showed every citation as 0:00 for videos indexed
    before citations existed. Checking one sample vector catches that and forces a re-index
    (upsert overwrites by the same deterministic vector IDs, so this self-heals without any
    manual cleanup).
    """
    stats = index.describe_index_stats()
    namespaces = stats.get("namespaces", {}) or {}
    ns = namespaces.get(video_id)
    if not ns or ns.get("vector_count", 0) == 0:
        return False

    vector = _sample_vector(index, video_id)
    if vector is None or vector.metadata is None:
        return False
    if any(field not in vector.metadata for field in _SCHEMA_SENTINEL_FIELDS):
        return False
    return vector.sparse_values is not None


def get_video_topic(video_id: str) -> str:
    """Reads back the per-video topic label generated once at ingestion time (see
    `_generate_topic`), for the Phase 5 input guardrail's off-topic check."""
    index = ensure_index()
    vector = _sample_vector(index, video_id)
    if vector is None or vector.metadata is None:
        return ""
    return vector.metadata.get("topic", "")


def _generate_topic(sample_text: str) -> str:
    """One quick LLM call, run once per video at ingestion time — not per question. Best-effort:
    an empty topic just makes the off-topic guardrail check less precise, never breaks ingestion."""
    try:
        # reasoning_effort="low" + a real token budget matters, not just latency: this call was
        # silently returning an empty topic for every video without it — gpt-oss-120b can spend
        # its entire max_tokens budget on internal reasoning before emitting any answer at all,
        # confirmed empirically at the original max_tokens=40 (see rag/guardrails/guards.py for
        # the full writeup of this same bug, found there first).
        llm = ChatGroq(model=config.CHAT_MODEL, temperature=0, max_tokens=200, reasoning_effort="low")
        prompt = (
            "In under 12 words, what is this video's topic? Reply with ONLY the topic phrase, "
            "no punctuation, no preamble.\n\n"
            f"Transcript excerpt:\n{sample_text[:2000]}"
        )
        response = llm.invoke(prompt)
        text = response.content if isinstance(response.content, str) else str(response.content)
        return text.strip().strip(".").strip('"')
    except Exception:
        return ""


def chunk_transcript_segments(segments: list[dict]) -> list[dict]:
    """Group timestamped transcript segments into ~CHUNK_SIZE-character chunks, each tagged with
    `start_ms` — the timestamp of its first segment. This is what makes timestamp citations
    possible (see specs/02-advanced-retrieval.md's original "future work" note, now built).

    Deliberately segment-boundary grouping rather than `RecursiveCharacterTextSplitter`'s
    arbitrary character splitting: every chunk's start_ms is an exact segment boundary, never
    interpolated. Overlap is approximated by carrying the trailing ~CHUNK_OVERLAP characters'
    worth of segments into the next chunk, rather than an exact character-count overlap.
    """
    chunks: list[dict] = []
    window: list[dict] = []
    window_len = 0

    def emit() -> None:
        if not window:
            return
        text = " ".join(s["text"].strip() for s in window if s["text"].strip())
        if text:
            chunks.append({"text": text, "start_ms": window[0]["offset_ms"]})

    for segment in segments:
        text = (segment.get("text") or "").strip()
        if not text:
            continue
        window.append(segment)
        window_len += len(text) + 1
        if window_len >= config.CHUNK_SIZE:
            emit()
            carry: list[dict] = []
            carry_len = 0
            for s in reversed(window):
                s_len = len(s["text"].strip()) + 1
                if carry_len + s_len > config.CHUNK_OVERLAP:
                    break
                carry.insert(0, s)
                carry_len += s_len
            window, window_len = carry, carry_len

    emit()
    return chunks


def embed_dense(texts: list[str], input_type: str) -> list[list[float]]:
    """input_type is "passage" for documents being indexed, "query" for a search query —
    Pinecone Inference's dense model uses this to produce better-matched embeddings for each."""
    pc = get_pinecone_client()
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), _EMBED_BATCH_SIZE):
        batch = texts[i : i + _EMBED_BATCH_SIZE]
        result = pc.inference.embed(
            model=config.EMBED_MODEL,
            inputs=batch,
            parameters={"input_type": input_type, "truncate": "END"},
        )
        embeddings.extend(r["values"] for r in result)
    return embeddings


def embed_sparse(texts: list[str], input_type: str) -> list[dict]:
    """Returns [{"indices": [...], "values": [...]}, ...] — the sparse-vector half of hybrid
    search (specs/02-advanced-retrieval.md). Response field names (`sparse_indices`/
    `sparse_values`) verified directly against a live call, not assumed."""
    pc = get_pinecone_client()
    sparse: list[dict] = []
    for i in range(0, len(texts), _EMBED_BATCH_SIZE):
        batch = texts[i : i + _EMBED_BATCH_SIZE]
        result = pc.inference.embed(
            model=config.SPARSE_EMBED_MODEL,
            inputs=batch,
            parameters={"input_type": input_type, "truncate": "END"},
        )
        sparse.extend({"indices": r["sparse_indices"], "values": r["sparse_values"]} for r in result)
    return sparse


def ensure_video_indexed(video_id: str, get_transcript_segments) -> None:
    """Chunk + embed + upsert a transcript into its namespace, unless it's already indexed.

    `get_transcript_segments` is a zero-arg callable, not a plain value — it's only invoked when
    the video isn't already indexed, so an already-indexed video never triggers a transcript-API
    request at all. This matters beyond efficiency: transcript fetches are rate/quota-limited
    (see the "deviations" note in specs/06-phased-rollout.md), so re-fetching on every question
    against an already-indexed video was needless extra exposure to that, not just wasted work.
    """
    index = ensure_index()
    if namespace_has_vectors(index, video_id):
        return

    segments = get_transcript_segments()
    chunks = chunk_transcript_segments(segments)
    texts = [c["text"] for c in chunks]
    dense_embeddings = embed_dense(texts, input_type="passage")
    sparse_embeddings = embed_sparse(texts, input_type="passage")
    # Computed once per video, not per question — stored redundantly on every chunk's metadata
    # (Pinecone namespaces don't have their own metadata store) so any sample fetch can read it
    # back cheaply. Used by the Phase 5 input guardrail's off-topic check.
    topic = _generate_topic(texts[0] if texts else "")

    vectors = [
        {
            "id": f"{video_id}-{i}",
            "values": dense,
            "sparse_values": sparse,
            "metadata": {
                "text": chunk["text"],
                "video_id": video_id,
                "start_ms": chunk["start_ms"],
                "topic": topic,
            },
        }
        for i, (chunk, dense, sparse) in enumerate(zip(chunks, dense_embeddings, sparse_embeddings))
    ]
    for i in range(0, len(vectors), _UPSERT_BATCH_SIZE):
        index.upsert(vectors=vectors[i : i + _UPSERT_BATCH_SIZE], namespace=video_id)
