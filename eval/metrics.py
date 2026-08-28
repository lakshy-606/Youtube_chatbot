"""DeepEval metric definitions. See specs/03-evaluation-deepeval.md for the fast-suite
(RAG triad) vs. full-suite design and why GEval uses explicit `evaluation_steps`, not freeform
`criteria` — DeepEval's own guidance is that steps score more reliably, and it was confirmed
directly: an ad hoc GEval call with a vague one-line criteria during development penalized a
factually-correct answer ("The capital of France is Paris.") down to 0.0 against expected "Paris"
purely for extra phrasing — exactly the failure mode explicit steps are meant to prevent.
"""
from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
    FaithfulnessMetric,
    GEval,
)
from deepeval.test_case import LLMTestCaseParams

from eval.judge_model import GroqJudgeModel

# Deliberately a *different* model than the app's own CHAT_MODEL (openai/gpt-oss-120b) — partly
# sound eval practice (a model grading its own outputs is a real bias risk), and partly forced by
# a real constraint found running this suite: this account's gpt-oss-120b free-tier daily token
# quota (200k TPD) was already exhausted by this session's own extensive testing of the app
# itself, which uses the same model/key. openai/gpt-oss-20b shares gpt-oss-120b's API surface
# (same reasoning_effort support) but draws from its own separate quota.
_judge = GroqJudgeModel(model="openai/gpt-oss-20b")

# --- Fast suite: the RAG triad — context relevance / groundedness / answer relevance ---
contextual_relevancy_metric = ContextualRelevancyMetric(model=_judge, threshold=0.5)
faithfulness_metric = FaithfulnessMetric(model=_judge, threshold=0.5)
answer_relevancy_metric = AnswerRelevancyMetric(model=_judge, threshold=0.5)

FAST_SUITE = [contextual_relevancy_metric, faithfulness_metric, answer_relevancy_metric]

# --- Full suite: adds precision/recall (need expected_output) + GEval correctness/completeness ---
contextual_precision_metric = ContextualPrecisionMetric(model=_judge, threshold=0.5)
contextual_recall_metric = ContextualRecallMetric(model=_judge, threshold=0.5)

correctness_metric = GEval(
    name="Correctness",
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
    evaluation_steps=[
        "Compare the factual claims in 'actual output' against 'expected output'.",
        "Penalize the response if it contradicts a fact stated in 'expected output'.",
        "Do not penalize different phrasing or wording of the same fact.",
        "Do not penalize omitted detail — that is covered by a separate completeness check.",
    ],
    model=_judge,
    threshold=0.5,
)

completeness_metric = GEval(
    name="Completeness",
    evaluation_params=[
        LLMTestCaseParams.INPUT,
        LLMTestCaseParams.ACTUAL_OUTPUT,
        LLMTestCaseParams.EXPECTED_OUTPUT,
    ],
    evaluation_steps=[
        "Identify every distinct sub-question or part within 'input'.",
        "Check whether 'actual output' addresses each part.",
        "Penalize the response if it ignores or only partially answers any part of a multi-part question.",
        "Do not penalize extra correct detail beyond what was asked.",
    ],
    model=_judge,
    threshold=0.5,
)

FULL_SUITE = FAST_SUITE + [
    contextual_precision_metric,
    contextual_recall_metric,
    correctness_metric,
    completeness_metric,
]
