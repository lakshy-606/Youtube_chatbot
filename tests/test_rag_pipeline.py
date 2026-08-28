"""rag/chains/rag_pipeline.py — the pure helper functions around the LLM/retrieval calls:
timestamp formatting, single-highest-score source selection, and guard error message cleanup."""
from rag.chains.rag_pipeline import _build_sources, _content_to_text, _format_timestamp, _guard_error_message


def test_format_timestamp_under_an_hour():
    assert _format_timestamp(0) == "0:00"
    assert _format_timestamp(65_000) == "1:05"
    assert _format_timestamp(3599_000) == "59:59"


def test_format_timestamp_over_an_hour():
    assert _format_timestamp(3600_000) == "1:00:00"
    assert _format_timestamp(3661_000) == "1:01:01"


def test_format_timestamp_negative_clamped_to_zero():
    assert _format_timestamp(-500) == "0:00"


def test_build_sources_empty_chunks():
    assert _build_sources("vid1", []) == []


def test_build_sources_picks_single_highest_score_chunk():
    chunks = [
        {"start_ms": 1000, "score": 0.4},
        {"start_ms": 65_000, "score": 0.9},  # highest score — this one should win
        {"start_ms": 30_000, "score": 0.7},
    ]
    sources = _build_sources("vid1", chunks)
    assert len(sources) == 1
    assert sources[0] == {
        "start_ms": 65_000,
        "label": "1:05",
        "url": "https://youtu.be/vid1?t=65",
    }


def test_content_to_text_plain_string():
    assert _content_to_text("hello") == "hello"


def test_content_to_text_content_block_list():
    content = [{"type": "text", "text": "hello "}, {"type": "reasoning", "text": "ignored"}, "world"]
    assert _content_to_text(content) == "hello world"


def test_content_to_text_unknown_shape_returns_empty():
    assert _content_to_text(None) == ""
    assert _content_to_text(42) == ""


def test_guard_error_message_strips_known_prefix():
    class FakeError(Exception):
        pass

    e = FakeError("Validation failed for field with errors: That question doesn't seem related.")
    assert _guard_error_message(e) == "That question doesn't seem related."


def test_guard_error_message_passes_through_unknown_shape():
    e = Exception("some other error")
    assert _guard_error_message(e) == "some other error"
