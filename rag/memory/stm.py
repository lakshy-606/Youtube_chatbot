"""Sliding-window short-term memory. A pure function, deliberately not a class or stored
state — see specs/05-memory-conversational-rag.md for why sliding-window over summarization or
full-history, and why there's no server-side session store at all (the client resends the full
message list every request; this module just windows it before it reaches the LLM).
"""
from __future__ import annotations


def extract_text(message: dict) -> str:
    """Pull the plain-text content out of a UIMessage's `parts` array."""
    parts = message.get("parts", [])
    return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


def trim_history(messages: list[dict], n_turns: int) -> list[dict]:
    """Keep only the last `n_turns` user/assistant exchanges (2 * n_turns messages)."""
    if n_turns <= 0:
        return []
    return messages[-(2 * n_turns):]


def format_history(messages: list[dict]) -> str:
    """Render trimmed history as plain text turns for the condense-question prompt."""
    lines = []
    for message in messages:
        text = extract_text(message)
        if not text:
            continue
        speaker = "Human" if message.get("role") == "user" else "Assistant"
        lines.append(f"{speaker}: {text}")
    return "\n".join(lines)
