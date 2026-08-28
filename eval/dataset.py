"""Golden dataset loading, and running the golden set through the *real* RAG pipeline
(`rag.chains.rag_pipeline.answer_for_eval`) to build DeepEval `LLMTestCase` objects.

Hand-curated (not `Synthesizer`-generated — see specs/03-evaluation-deepeval.md for why: the
Synthesizer's context-construction step needs its own embedding model, which would have meant
building a second custom DeepEval model wrapper just for one-time dataset generation, for a
golden set small enough that hand-curation is simpler and gives more deliberate coverage — e.g.
a golden specifically designed to test the "I don't know" faithfulness path) — written against
the frozen fixtures in data/eval/fixtures/, so what the golden set was written against stays
reproducible even if the live YouTube transcript ever changes.
"""
from __future__ import annotations

import asyncio
import json
from functools import lru_cache
from pathlib import Path

from deepeval.test_case import LLMTestCase

from rag.chains.rag_pipeline import answer_for_eval

_DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "eval" / "golden_dataset.json"


def load_goldens() -> list[dict]:
    return json.loads(_DATASET_PATH.read_text())


async def _build_test_case(golden: dict) -> LLMTestCase:
    result = await answer_for_eval(golden["video_id"], golden["input"])
    return LLMTestCase(
        input=golden["input"],
        actual_output=result["actual_output"],
        expected_output=golden["expected_output"],
        retrieval_context=result["retrieval_context"],
    )


@lru_cache(maxsize=1)
def build_test_cases() -> tuple[LLMTestCase, ...]:
    """Runs every golden through the real pipeline once per process, memoized — metrics are then
    measured against these fixed test cases rather than re-running retrieval+generation once per
    metric (which would be both slow and a source of run-to-run variance in what's being scored)."""
    goldens = load_goldens()

    async def _build_all() -> list[LLMTestCase]:
        return [await _build_test_case(g) for g in goldens]

    return tuple(asyncio.run(_build_all()))
