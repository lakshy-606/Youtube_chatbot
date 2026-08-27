"""rag/memory/stm.py — sliding-window short-term memory, pure functions."""
from rag.memory.stm import extract_text, format_history, trim_history


def _msg(role, text):
    return {"role": role, "parts": [{"type": "text", "text": text}]}


def test_extract_text_joins_text_parts_and_ignores_others():
    message = {
        "role": "user",
        "parts": [
            {"type": "text", "text": "Hello "},
            {"type": "data-status", "message": "irrelevant"},
            {"type": "text", "text": "world"},
        ],
    }
    assert extract_text(message) == "Hello world"


def test_extract_text_handles_missing_parts():
    assert extract_text({"role": "user"}) == ""


def test_trim_history_keeps_last_n_turns():
    messages = [_msg("user", f"q{i}") if i % 2 == 0 else _msg("assistant", f"a{i}") for i in range(10)]
    trimmed = trim_history(messages, n_turns=2)
    assert trimmed == messages[-4:]


def test_trim_history_zero_or_negative_returns_empty():
    messages = [_msg("user", "hi")]
    assert trim_history(messages, n_turns=0) == []
    assert trim_history(messages, n_turns=-1) == []


def test_trim_history_fewer_messages_than_window():
    messages = [_msg("user", "hi")]
    assert trim_history(messages, n_turns=4) == messages


def test_format_history_renders_speaker_labels_and_skips_empty():
    messages = [_msg("user", "What's this video about?"), _msg("assistant", "It's about bears."), _msg("user", "")]
    assert format_history(messages) == "Human: What's this video about?\nAssistant: It's about bears."
