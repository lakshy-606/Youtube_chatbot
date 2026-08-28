"""rag/retrieval/retrievers.py — hybrid score scaling, reciprocal rank fusion, and the rerank
fail-soft fallback (Pinecone's own query/rerank calls are mocked; nothing here hits the network)."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from rag.retrieval.retrievers import (
    _hybrid_score_norm,
    _rerank,
    _reciprocal_rank_fusion,
    format_context,
)


def test_hybrid_score_norm_alpha_one_is_dense_only():
    dense = [1.0, 2.0]
    sparse = {"indices": [0, 1], "values": [1.0, 1.0]}
    hdense, hsparse = _hybrid_score_norm(dense, sparse, alpha=1.0)
    assert hdense == [1.0, 2.0]
    assert hsparse["values"] == [0.0, 0.0]


def test_hybrid_score_norm_alpha_zero_is_sparse_only():
    dense = [1.0, 2.0]
    sparse = {"indices": [0, 1], "values": [1.0, 1.0]}
    hdense, hsparse = _hybrid_score_norm(dense, sparse, alpha=0.0)
    assert hdense == [0.0, 0.0]
    assert hsparse["values"] == [1.0, 1.0]


def test_hybrid_score_norm_balanced_blend():
    hdense, hsparse = _hybrid_score_norm([2.0], {"indices": [0], "values": [2.0]}, alpha=0.5)
    assert hdense == [1.0]
    assert hsparse["values"] == [1.0]


@pytest.mark.parametrize("bad_alpha", [-0.1, 1.1])
def test_hybrid_score_norm_rejects_out_of_range_alpha(bad_alpha):
    with pytest.raises(ValueError):
        _hybrid_score_norm([1.0], {"indices": [0], "values": [1.0]}, alpha=bad_alpha)


def test_reciprocal_rank_fusion_favors_chunks_ranked_high_in_multiple_lists():
    list_a = [{"id": "x"}, {"id": "y"}, {"id": "z"}]
    list_b = [{"id": "y"}, {"id": "x"}, {"id": "w"}]
    fused = _reciprocal_rank_fusion([list_a, list_b])
    fused_ids = [c["id"] for c in fused]
    # "x" and "y" each appear near the top of both lists, so both should outrank "z"/"w", which
    # only appear once and near the bottom.
    assert fused_ids.index("x") < fused_ids.index("z")
    assert fused_ids.index("y") < fused_ids.index("w")


def test_reciprocal_rank_fusion_single_list_preserves_order():
    chunks = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    assert [c["id"] for c in _reciprocal_rank_fusion([chunks])] == ["a", "b", "c"]


def test_format_context_joins_chunk_text_with_blank_lines():
    chunks = [{"text": "first chunk"}, {"text": "second chunk"}]
    assert format_context(chunks) == "first chunk\n\nsecond chunk"


def test_format_context_empty():
    assert format_context([]) == ""


def test_rerank_empty_chunks_short_circuits():
    assert _rerank("question", [], top_n=5) == []


def test_rerank_falls_back_to_original_order_on_error():
    chunks = [{"id": "a", "text": "t1", "score": 0.1}, {"id": "b", "text": "t2", "score": 0.2}]
    fake_client = SimpleNamespace(
        inference=SimpleNamespace(rerank=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("quota exhausted")))
    )
    with patch("rag.retrieval.retrievers.get_pinecone_client", return_value=fake_client):
        result = _rerank("question", chunks, top_n=1)
    # Best-effort fallback: pre-rerank ordering, trimmed to top_n — never raises.
    assert result == chunks[:1]
