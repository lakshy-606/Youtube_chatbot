# 03 — Evaluation (DeepEval)

Evaluation is a **local/CI dev-time process**, not part of the deployed Vercel app. `eval/*` imports
`rag/` directly — it never calls the live `/api/chat` endpoint, so eval runs are deterministic and
don't depend on (or affect) the deployment.

**Judge model — built, `eval/judge_model.py`**: `GroqJudgeModel`, a custom `DeepEvalBaseLLM`
subclass, deliberately not DeepEval's built-in `LiteLLMModel` gateway (which would have been the
obvious choice — same `litellm`/Groq routing) because that one forces schema-based structured
output via tool-calling, and `openai/gpt-oss-120b` via Groq doesn't reliably comply with a forced
`tool_choice` (confirmed empirically: `litellm.exceptions.BadRequestError: ... Tool choice is
required, but model did not call a tool`). `DeepEvalBaseLLM`'s own `generate_with_schema()`
default implementation catches the `TypeError` from a `generate()` that takes no `schema` param
and falls back to plain-text + DeepEval's own `trimAndLoadJson` parsing — writing `generate()`
that way sidesteps the incompatibility for free.

Uses `openai/gpt-oss-20b` as the judge, not the app's own `openai/gpt-oss-120b` — partly sound
practice (a model grading its own outputs is a bias risk), partly forced: this account's
gpt-oss-120b free-tier daily quota was exhausted by this session's own testing of the app itself
(see [[06-phased-rollout]]'s Phase 6 notes for the full diagnosis, including the rate-limit/
timeout issues hit and fixed along the way — an instance-level semaphore + pacing delay inside
the judge model, and `DEEPEVAL_DISABLE_TIMEOUTS=1`). An open-weight judge model is a legitimate
but real quality tradeoff vs. GPT-4/Claude-class judges — DeepEval's own research on G-Eval
reliability was largely validated against frontier models, so treat absolute threshold values
loosely and calibrate them against this judge specifically rather than trusting published
benchmarks.

## Golden dataset — built

- 2 fixed benchmark videos (`cTQ3Ko9ZKg8`, a substantive nature-documentary narration; `jNQXAC9IVRw`,
  a tiny/sparse edge case), transcripts frozen as `.txt` fixtures under `data/eval/fixtures/`.
  **Never live-fetched during eval** — live transcript fetches are the single biggest source of
  eval flakiness (rate limits, region locks); freezing removes that variable entirely.
- **Hand-curated, not `Synthesizer`-generated** — deviation from the original plan. The
  `Synthesizer`'s context-construction step needs its own custom embedding-model wrapper (it
  defaults to OpenAI too, same problem as the judge), which wasn't worth building for a golden set
  small enough that hand-curation gives more deliberate coverage: a golden specifically for the
  "I don't know" faithfulness path, one specifically multi-part for completeness, etc. — see
  [[06-phased-rollout]]'s Phase 6 notes.
- 16 examples total across the two videos (`data/eval/golden_dataset.json`, loaded by
  `eval/dataset.py`), tagged `factual` / `multi-part` / `unanswerable` for documentation.
- `eval/dataset.py:build_test_cases()` runs every golden through the *real* pipeline
  (`rag.chains.rag_pipeline.answer_for_eval`) once per process (memoized) to build each
  `LLMTestCase`'s `actual_output`/`retrieval_context` — not pre-computed/frozen, so eval measures
  current retrieval+generation behavior, not a snapshot.

## Metric suites

Split into two suites so routine runs stay cheap; the full suite (with GEval + reference-based
metrics) is for occasional/pre-release runs.

### Fast suite — "RAG triad" (run often, e.g. every retrieval-affecting change)

Reference-free — no `expected_output` needed, works directly against `input` / `actual_output` /
`retrieval_context`:

| Metric | DeepEval class | What it checks |
|---|---|---|
| Context relevance | `ContextualRelevancyMetric` | did retrieval return chunks relevant to the question? |
| Groundedness / faithfulness | `FaithfulnessMetric` | is the answer supported by the retrieved context (not hallucinated)? |
| Answer relevance | `AnswerRelevancyMetric` | does the answer actually address the question asked? |

These three *are* the RAG triad — reported together as one composite view of retrieval quality
end-to-end (a concept from TruLens, implemented here with DeepEval's metric classes).

### Full suite — precision/recall + correctness/completeness (run occasionally, e.g. pre-merge/pre-release)

Adds reference-based metrics requiring `expected_output` / a reference context in the golden set:

| Metric | DeepEval class | What it checks |
|---|---|---|
| Precision | `ContextualPrecisionMetric` | are the *relevant* retrieved chunks ranked above irrelevant ones? |
| Recall | `ContextualRecallMetric` | did retrieval surface everything needed to fully answer, per the reference? |
| Correctness | `GEval` (custom) | does the answer match the expected answer's factual content? |
| Completeness | `GEval` (custom) | does the answer address *every* part of a (possibly multi-part) question? |

`GEval` criteria use explicit `evaluation_steps` (a numbered chain-of-thought rubric), not
freeform `criteria` text — DeepEval's own guidance is that steps produce materially more reliable
judge scoring than a single criteria sentence.

- **Correctness** — `evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT,
  LLMTestCaseParams.EXPECTED_OUTPUT]`. Steps: (1) compare the factual claims in actual vs. expected
  output, (2) penalize contradictions, (3) do not penalize different phrasing/wording of the same
  fact, (4) do not penalize omitted detail already covered by the completeness metric.
- **Completeness** — `evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT,
  LLMTestCaseParams.EXPECTED_OUTPUT]`. Steps: (1) identify every distinct sub-question/part in the
  input, (2) check whether the actual output addresses each part, (3) penalize partially-answered
  or ignored parts, (4) do not penalize extra correct detail beyond what was asked.

## Running

Requires Python ≥3.10 — `deepeval` fails to *import* on 3.9 (module-level `X | Y` syntax), not
just a metadata restriction. Local dev now runs 3.12 (`uv python install 3.12`) for this reason —
see [[06-phased-rollout]]. Install the eval-only deps on top of the root ones:
`pip install -r eval/requirements.txt` (deliberately not merged into the root `requirements.txt`,
which Vercel packages into the deployed function — evaluation never runs there).

```bash
# run as a module, not a script — eval/dataset.py etc. are package-relative imports, and
# `python eval/run_eval.py` puts eval/ itself on sys.path instead of the repo root
python -m eval.run_eval             # fast suite (RAG triad)
python -m eval.run_eval --full      # full suite
deepeval test run eval/test_rag_metrics.py     # pytest-native, fast suite by default
DEEPEVAL_FULL_SUITE=true deepeval test run eval/test_rag_metrics.py   # + full suite
```

**Status**: every piece has been individually verified against real API calls (a real pipeline
answer, a real metric score with sensible reasoning, the judge model avoiding the tool-calling
incompatibility) — what hasn't been verified yet is one complete run across the full 16-example
golden set. First blocked by the app's own `gpt-oss-120b` daily quota (exhausted by this session's
testing of the app itself); after that recovered (Phase 7), a real attempt got much further before
hitting the **judge model's** (`gpt-oss-20b`) own daily quota instead, also nearly exhausted by
this session's cumulative testing. That attempt also surfaced and fixed a real bug in
`eval/judge_model.py`'s rate-limit retry parsing (it mis-read Groq's `"try again in 4m19.2s"`
minute+second wait format as 19.2s, burning through all retries early) — see [[06-phased-rollout]]'s
Phase 6/7 notes for the full diagnosis and what to re-run once `gpt-oss-20b`'s quota recovers.

## Related specs

[[00-overview]] · [[01-architecture]] · [[06-phased-rollout]]
