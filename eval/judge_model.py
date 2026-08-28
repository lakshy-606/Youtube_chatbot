"""A custom DeepEval judge model wrapping our own `ChatGroq` — not DeepEval's built-in LiteLLM
gateway model, because that one forces schema-based structured output via tool-calling, and
`openai/gpt-oss-120b` via Groq doesn't reliably comply with a forced `tool_choice` — confirmed
empirically, not assumed:

    litellm.exceptions.BadRequestError: GroqException - {"error": {"message": "Tool choice is
    required, but model did not call a tool", "code": "tool_use_failed", ...}}

`DeepEvalBaseLLM`'s own `generate_with_schema()` default implementation (see
`deepeval/models/base_model.py`) falls back to plain `generate()` + DeepEval's own text-based JSON
parsing (`trimAndLoadJson`) whenever `generate()` doesn't accept a `schema` kwarg — so implementing
a plain `generate(prompt) -> str` here, with no `schema` parameter, gets that fallback for free,
sidestepping the tool-calling incompatibility entirely. DeepEval's own metric prompts already ask
for JSON in the prompt text itself; this model just needs to answer them.

Rate limiting: several of DeepEval's own metrics (e.g. ContextualRelevancy, Faithfulness) fire an
internal `asyncio.gather` burst of one judge call *per retrieved chunk/claim* when scoring a
single test case. Confirmed empirically that this blows through Groq's free-tier 8000 TPM limit
for gpt-oss-120b even with `eval/run_eval.py`'s outer `AsyncConfig(max_concurrent=1)` (that only
throttles across test cases, not a metric's own internal concurrency) AND even with the Groq
SDK's own built-in retry (`max_retries=10` still weren't enough — its default backoff doesn't
space concurrent retries far enough apart for this burst shape). Since every judge call funnels
through this one model instance regardless of how many concurrent tasks DeepEval spawns, an
instance-level semaphore + a real pacing delay serializes and paces every call at the source —
the one place that reliably reaches all of them.
"""
from __future__ import annotations

import asyncio
import re
import time

from deepeval.models.base_model import DeepEvalBaseLLM
from groq import RateLimitError
from langchain_groq import ChatGroq

from rag import config

_MIN_INTERVAL_SECONDS = 3.0  # paces calls well under the 8000 TPM budget, not just reactive retry
_MAX_RETRIES = 6
# Groq's RateLimitError message states the wait as "Xm Y.Zs" for longer (daily-quota-scale) waits
# and just "Y.Zs" for short (per-minute-scale) ones — e.g. "try again in 4m19.2s" vs "try again in
# 12.3s". A real bug found in Phase 7: an earlier version of this regex (`r"try again in
# ([\d.]+)s"`) only ever captured the seconds group, so "4m19.2s" parsed as a 19.2s wait instead
# of the real 259.2s — confirmed empirically against a live TPD-exhaustion error, where this
# silently burned through all `_MAX_RETRIES` attempts in under 2 minutes instead of waiting out
# the actual ~4m19s window, turning a recoverable rate limit into a hard failure.
_RETRY_AFTER_RE = re.compile(r"try again in (?:(\d+)h)?(?:(\d+)m)?([\d.]+)s")


def _parse_retry_after_seconds(error_message: str, default: float) -> float:
    """Extract Groq's suggested wait time from a RateLimitError message, handling both the plain
    "Y.Zs" and the "XhYmZ.Ws" forms. Falls back to `default` if the message doesn't match the
    expected shape at all (defensive — a wording change upstream should degrade to a fixed
    backoff, not raise)."""
    match = _RETRY_AFTER_RE.search(error_message)
    if not match:
        return default
    hours, minutes, seconds = match.groups()
    total = float(seconds)
    if minutes:
        total += float(minutes) * 60
    if hours:
        total += float(hours) * 3600
    return total + 1.0  # small safety margin so a retry doesn't land exactly on the boundary


def _content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block if isinstance(block, str) else block.get("text", "")
            for block in content
            if isinstance(block, str) or block.get("type") == "text"
        )
    return ""


class GroqJudgeModel(DeepEvalBaseLLM):
    """The eval judge — deliberately separate from the app's own `_get_llm()` in
    rag/chains/rag_pipeline.py, even though both wrap ChatGroq, because this one is tuned
    specifically for DeepEval's long, structured judging prompts (wide max_tokens, aggressive
    rate-limit pacing) rather than the app's short classification calls or long-form streamed
    answers.
    """

    def __init__(self, model: str | None = None):
        self._model_name = model or config.CHAT_MODEL
        self._semaphore = asyncio.Semaphore(1)
        self._last_call_at = 0.0
        super().__init__(model=self._model_name)

    def load_model(self) -> ChatGroq:
        # reasoning_effort="low" + a wide token budget: gpt-oss-120b can burn its entire
        # max_tokens budget on internal chain-of-thought before emitting any answer at all
        # without this — the same bug found and fixed in rag/guardrails/guards.py and
        # rag/ingestion/indexing.py (see specs/06-phased-rollout.md's Phase 5 notes). DeepEval's
        # own evaluation prompts are long/structured, the same shape that triggered it there.
        return ChatGroq(
            model=self._model_name,
            temperature=0,
            max_tokens=2048,
            reasoning_effort="low",
            max_retries=2,  # the pacing below does the real work; this just catches the odd blip
        )

    def generate(self, prompt: str) -> str:
        return _content_to_text(self.model.invoke(prompt).content)

    async def a_generate(self, prompt: str) -> str:
        async with self._semaphore:
            # Pace calls under the semaphore, not just serialize them — serialized-but-back-to-
            # back calls can still burn through a per-minute token budget.
            elapsed = time.monotonic() - self._last_call_at
            if elapsed < _MIN_INTERVAL_SECONDS:
                await asyncio.sleep(_MIN_INTERVAL_SECONDS - elapsed)

            last_error: RateLimitError | None = None
            for attempt in range(_MAX_RETRIES):
                try:
                    response = await self.model.ainvoke(prompt)
                    self._last_call_at = time.monotonic()
                    return _content_to_text(response.content)
                except RateLimitError as e:
                    last_error = e
                    wait = _parse_retry_after_seconds(str(e), default=5.0 * (attempt + 1))
                    await asyncio.sleep(wait)
            self._last_call_at = time.monotonic()
            raise last_error

    def get_model_name(self) -> str:
        return self._model_name
