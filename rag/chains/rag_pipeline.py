"""Ingest-if-needed -> [condense] -> guard(in) -> [multi-query] -> hybrid retrieve -> [rerank] ->
prompt -> streamed answer -> guard(out) -> suggestions.

Phase 4 (specs/02-advanced-retrieval.md) added hybrid dense+sparse retrieval (always on), optional
multi-query expansion, and optional hosted reranking, plus lightweight SSE status events. Phase 5
(specs/04-guardrails.md) adds LLM-based input/output guardrails: the input guard runs on the
*condensed* question and can genuinely block the turn (raises PipelineError, same as any other
user-facing error); the output guard runs on the *complete* generated answer, after it has already
streamed — it can't un-send tokens already shown, so a failure there surfaces as a flag on the
message rather than a block. See specs/04-guardrails.md for why that tradeoff was accepted.

`answer_question` yields a stream of tagged event dicts rather than plain text, so api/chat.py can
map each to the right AI SDK Data Stream Protocol event (text-delta vs. custom data parts):
  {"type": "status", "message": "..."}                     # ephemeral progress, not persisted
  {"type": "sources", "sources": [{"start_ms": int, "label": "2:34", "url": "..."}]}
  {"type": "text", "text": "..."}                          # one per streamed token/chunk
  {"type": "warning", "message": "..."}                    # output guard flag (non-blocking)
  {"type": "suggestions", "suggestions": ["...", "..."]}
"""
from collections.abc import AsyncIterator

from guardrails.errors import ValidationError as GuardValidationError
from langchain_groq import ChatGroq

from rag import config
from rag.chains.prompts import (
    ANSWER_PROMPT,
    CONDENSE_QUESTION_PROMPT,
    MULTIQUERY_PROMPT,
    SUGGESTIONS_PROMPT,
)
from rag.guardrails.guards import build_input_guard, build_output_guard
from rag.ingestion.indexing import ensure_video_indexed, get_video_topic
from rag.ingestion.transcript import TranscriptError, extract_video_id, fetch_transcript_segments
from rag.memory.stm import extract_text, format_history, trim_history
from rag.retrieval.retrievers import format_context, retrieve

_GUARD_ERROR_PREFIX = "Validation failed for field with errors: "


def _guard_error_message(e: GuardValidationError) -> str:
    text = str(e)
    return text[len(_GUARD_ERROR_PREFIX) :] if text.startswith(_GUARD_ERROR_PREFIX) else text


class PipelineError(Exception):
    """A user-facing error (bad video, no transcript, etc.) — caught in api/chat.py and surfaced
    as an SSE `error` event rather than a crash."""


def _get_llm(streaming: bool = True) -> ChatGroq:
    # Non-streaming calls here are all short, structured, non-creative completions (condense,
    # multi-query, suggestions) — the same shape as the guardrail classifiers that turned out to
    # silently return empty content at default reasoning effort (gpt-oss-120b can burn its whole
    # max_tokens budget on internal chain-of-thought before emitting anything at all; see
    # rag/guardrails/guards.py for the full writeup). `reasoning_effort="low"` avoids that here
    # too — full effort is kept for the streaming answer itself, where reasoning quality matters.
    kwargs = {} if streaming else {"reasoning_effort": "low"}
    return ChatGroq(
        model=config.CHAT_MODEL,
        temperature=config.CHAT_TEMPERATURE,
        streaming=streaming,
        max_tokens=1024,
        **kwargs,
    )


def _content_to_text(content) -> str:
    """AIMessageChunk.content is usually a plain string, but some LangChain chat model wrappers
    can yield a list of content blocks — handle both defensively rather than assume one shape."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block if isinstance(block, str) else block.get("text", "")
            for block in content
            if isinstance(block, str) or block.get("type") == "text"
        )
    return ""


def _condense_question(history_text: str, question: str) -> str:
    """Rephrase a follow-up into a standalone question using recent history. One extra (small,
    non-streamed) LLM call — skipped entirely when there's no history yet (first turn)."""
    llm = _get_llm(streaming=False)
    prompt = CONDENSE_QUESTION_PROMPT.format(chat_history=history_text, question=question)
    response = llm.invoke(prompt)
    condensed = _content_to_text(response.content).strip()
    return condensed or question


def _format_timestamp(ms: float) -> str:
    total_seconds = int(max(0, ms) // 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _build_sources(video_id: str, chunks: list[dict]) -> list[dict]:
    """Just the single highest-scoring chunk — one confident citation reads cleaner than several
    approximate ones, per user feedback. Returns a list (length 0 or 1) so the frontend doesn't
    need a special case for "one vs. many"."""
    if not chunks:
        return []
    best = max(chunks, key=lambda c: c.get("score", 0))
    seconds = int(best.get("start_ms", 0) // 1000)
    return [
        {
            "start_ms": best.get("start_ms", 0),
            "label": _format_timestamp(best.get("start_ms", 0)),
            "url": f"https://youtu.be/{video_id}?t={seconds}",
        }
    ]


def _generate_query_variants(question: str) -> list[str]:
    """RAG-Fusion-style paraphrases for wider recall — best-effort, same reasoning as
    _generate_suggestions: a failure here should degrade to single-query retrieval, not break
    the turn."""
    try:
        llm = _get_llm(streaming=False)
        prompt = MULTIQUERY_PROMPT.format(question=question, count=config.MULTIQUERY_COUNT)
        response = llm.invoke(prompt)
        text = _content_to_text(response.content)
        lines = [line.strip(" -•\t0123456789.)") for line in text.splitlines()]
        return [line for line in lines if line][: config.MULTIQUERY_COUNT]
    except Exception:
        return []


def _generate_suggestions(context: str, question: str, answer: str) -> list[str]:
    """Best-effort — a bad/empty response here should never break the answer that already
    streamed, so failures are swallowed rather than raised as a PipelineError."""
    try:
        llm = _get_llm(streaming=False)
        prompt = SUGGESTIONS_PROMPT.format(context=context, question=question, answer=answer)
        response = llm.invoke(prompt)
        text = _content_to_text(response.content)
        lines = [line.strip(" -•\t") for line in text.splitlines()]
        return [line for line in lines if line][:3]
    except Exception:
        return []


async def answer_question(video_id_or_url: str, messages: list[dict]) -> AsyncIterator[dict]:
    """`messages` is the full UIMessage list from the client (see rag/memory/stm.py) — the last
    one is the current question, everything before it is history."""
    video_id = extract_video_id((video_id_or_url or "").strip())
    if not video_id:
        raise PipelineError("No video ID or URL provided.")

    windowed = trim_history(messages, config.N_TURNS + 1)  # +1 to include the current turn
    if not windowed:
        raise PipelineError("No question provided.")
    question = extract_text(windowed[-1])
    history = windowed[:-1]
    if not question:
        raise PipelineError("No question provided.")

    def get_transcript_segments() -> list[dict]:
        # Only called by ensure_video_indexed when this video isn't already indexed — an
        # already-indexed video never touches the transcript service again. See
        # ensure_video_indexed's docstring for why that matters beyond efficiency.
        try:
            return fetch_transcript_segments(video_id)
        except TranscriptError as e:
            raise PipelineError(str(e))

    ensure_video_indexed(video_id, get_transcript_segments)

    if history:
        yield {"type": "status", "message": "Reading the conversation so far…"}
    standalone_question = (
        _condense_question(format_history(history), question) if history else question
    )

    topic = get_video_topic(video_id)
    try:
        build_input_guard(topic).validate(standalone_question)
    except GuardValidationError as e:
        raise PipelineError(_guard_error_message(e))

    query_variants: list[str] = []
    if config.MULTIQUERY_ENABLED:
        yield {"type": "status", "message": "Expanding your question…"}
        query_variants = _generate_query_variants(standalone_question)

    yield {"type": "status", "message": "Searching the transcript…"}
    chunks = retrieve(video_id, standalone_question, query_variants=query_variants)
    context = format_context(chunks)

    sources = _build_sources(video_id, chunks)
    if sources:
        yield {"type": "sources", "sources": sources}

    prompt = ANSWER_PROMPT.format(context=context, question=standalone_question)
    llm = _get_llm()
    answer_parts: list[str] = []
    async for chunk in llm.astream(prompt):
        text = _content_to_text(chunk.content)
        if text:
            answer_parts.append(text)
            yield {"type": "text", "text": text}

    answer_text = "".join(answer_parts)
    try:
        build_output_guard(context).validate(answer_text)
    except GuardValidationError as e:
        yield {"type": "warning", "message": _guard_error_message(e)}

    suggestions = _generate_suggestions(context, standalone_question, answer_text)
    if suggestions:
        yield {"type": "suggestions", "suggestions": suggestions}


async def answer_for_eval(video_id_or_url: str, question: str) -> dict:
    """Phase 6 (specs/03-evaluation-deepeval.md): a separate, simpler entry point for `eval/*`,
    not a parameterized variant of `answer_question`. Deliberately bypasses guardrails, condense,
    multi-query, and suggestions — eval measures retrieval+generation quality against a golden
    dataset of already-standalone questions, and guardrail behavior is verified separately via the
    adversarial checks in specs/04-guardrails.md (conflating the two would fail quality metrics
    for the wrong reason on a blocked golden-set question). Still calls the exact same `retrieve`/
    `format_context`/`ANSWER_PROMPT`/`_get_llm` building blocks as the real pipeline, non-streamed,
    so eval is measuring the real retrieval/generation path, not a reimplementation of it.

    Returns {"actual_output": str, "retrieval_context": list[str]} — directly the two fields
    DeepEval's contextual metrics need beyond the golden's own `input`/`expected_output`.
    """
    video_id = extract_video_id((video_id_or_url or "").strip())

    def get_transcript_segments() -> list[dict]:
        return fetch_transcript_segments(video_id)

    ensure_video_indexed(video_id, get_transcript_segments)

    chunks = retrieve(video_id, question)
    context = format_context(chunks)
    prompt = ANSWER_PROMPT.format(context=context, question=question)
    response = _get_llm(streaming=False).invoke(prompt)

    return {
        "actual_output": _content_to_text(response.content).strip(),
        "retrieval_context": [c["text"] for c in chunks],
    }
