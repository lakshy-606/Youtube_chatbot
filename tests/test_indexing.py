"""rag/ingestion/indexing.py — chunk_transcript_segments() (pure) and namespace_has_vectors()
(schema self-healing check, exercised against a fake Pinecone index stub — no network)."""
from types import SimpleNamespace

from rag import config
from rag.ingestion.indexing import chunk_transcript_segments, namespace_has_vectors


def _segment(text, offset_ms):
    return {"text": text, "offset_ms": offset_ms, "duration_ms": 1000}


def test_chunk_transcript_segments_basic_grouping(monkeypatch):
    monkeypatch.setattr(config, "CHUNK_SIZE", 20)
    monkeypatch.setattr(config, "CHUNK_OVERLAP", 5)
    segments = [
        _segment("one two three", 0),
        _segment("four five six", 2000),
        _segment("seven eight nine", 4000),
    ]
    chunks = chunk_transcript_segments(segments)

    assert len(chunks) >= 2
    # Every chunk's start_ms is an exact segment boundary (0, 2000, or 4000) — never interpolated.
    assert all(c["start_ms"] in (0, 2000, 4000) for c in chunks)
    # First chunk starts at the very first segment.
    assert chunks[0]["start_ms"] == 0


def test_chunk_transcript_segments_drops_blank_segments(monkeypatch):
    monkeypatch.setattr(config, "CHUNK_SIZE", 1000)
    monkeypatch.setattr(config, "CHUNK_OVERLAP", 200)
    segments = [_segment("  ", 0), _segment("real text", 1000)]
    chunks = chunk_transcript_segments(segments)
    assert len(chunks) == 1
    assert chunks[0]["text"] == "real text"
    assert chunks[0]["start_ms"] == 1000


def test_chunk_transcript_segments_empty_input():
    assert chunk_transcript_segments([]) == []


def _fake_index(*, namespaces, vector=None):
    return SimpleNamespace(
        describe_index_stats=lambda: {"namespaces": namespaces},
        fetch=lambda ids, namespace: SimpleNamespace(vectors={ids[0]: vector} if vector else {}),
    )


def test_namespace_has_vectors_false_when_namespace_missing():
    index = _fake_index(namespaces={})
    assert namespace_has_vectors(index, "vid1") is False


def test_namespace_has_vectors_false_when_vector_count_zero():
    index = _fake_index(namespaces={"vid1": {"vector_count": 0}})
    assert namespace_has_vectors(index, "vid1") is False


def test_namespace_has_vectors_false_on_old_schema_missing_sentinel_field():
    # Indexed before `topic` (Phase 5) existed — should be treated as stale, not already-indexed.
    vector = SimpleNamespace(metadata={"start_ms": 0}, sparse_values={"indices": [], "values": []})
    index = _fake_index(namespaces={"vid1": {"vector_count": 3}}, vector=vector)
    assert namespace_has_vectors(index, "vid1") is False


def test_namespace_has_vectors_false_when_sparse_values_missing():
    # Indexed before Phase 4 hybrid search added sparse_values.
    vector = SimpleNamespace(metadata={"start_ms": 0, "topic": "bears"}, sparse_values=None)
    index = _fake_index(namespaces={"vid1": {"vector_count": 3}}, vector=vector)
    assert namespace_has_vectors(index, "vid1") is False


def test_namespace_has_vectors_true_on_current_schema():
    vector = SimpleNamespace(
        metadata={"start_ms": 0, "topic": "bears"}, sparse_values={"indices": [1], "values": [0.5]}
    )
    index = _fake_index(namespaces={"vid1": {"vector_count": 3}}, vector=vector)
    assert namespace_has_vectors(index, "vid1") is True
