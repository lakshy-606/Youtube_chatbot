"""DeepEval pytest suite. See specs/03-evaluation-deepeval.md.

Fast suite (RAG triad — context relevance, faithfulness, answer relevance), run often:

    deepeval test run eval/test_rag_metrics.py

Full suite (adds precision/recall + GEval correctness/completeness — several more LLM-judge
calls per test case), gated behind an env var so routine runs stay cheap:

    DEEPEVAL_FULL_SUITE=true deepeval test run eval/test_rag_metrics.py

Deliberately calls `rag.chains.rag_pipeline.answer_for_eval` (via `eval.dataset.build_test_cases`)
rather than going through `api/chat.py` or a live deployment — no guardrails, no streaming, no
conversational history, just the retrieval+generation quality this suite measures. See
specs/06-phased-rollout.md's sequencing rationale for why guardrail behavior is verified
separately (specs/04-guardrails.md's adversarial checks) instead of conflated with these metrics.
"""
import os

import pytest
from deepeval import assert_test

from eval.dataset import build_test_cases
from eval.metrics import FAST_SUITE, FULL_SUITE

_FULL_SUITE_ENABLED = os.environ.get("DEEPEVAL_FULL_SUITE", "false").lower() == "true"


@pytest.mark.parametrize("test_case", build_test_cases())
def test_rag_triad(test_case):
    assert_test(test_case, FAST_SUITE)


@pytest.mark.skipif(not _FULL_SUITE_ENABLED, reason="set DEEPEVAL_FULL_SUITE=true to run")
@pytest.mark.parametrize("test_case", build_test_cases())
def test_full_suite(test_case):
    assert_test(test_case, FULL_SUITE)
