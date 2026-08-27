# 04 — Guardrails (Guardrails AI) — built, Phase 5

## API

`rag/guardrails/guards.py`. Confirmed live against the actual installed package (0.6.8), not
docs alone: `Guard().use(ValidatorInstance(...), on_fail="exception")`, `guard.validate(value)`
(not `.parse()`), custom validators via `@register_validator(name=..., data_type="string")` on a
`Validator` subclass returning `PassResult()`/`FailResult(error_message=...)`.

## Why every check ended up as a custom validator, not a Hub one

Every Guardrails Hub validator that could plausibly cover these checks was inspected live on PyPI
(`requires_dist`) before deciding, not assumed from naming:

| Hub package | Looked LLM-based? | Actually requires |
|---|---|---|
| `guardrails-ai-detect-prompt-injection` | No (rebuff-based) | `rebuff` → hardcoded `openai` dependency + old `pinecone-client<4.0.0` (would conflict with this project's `pinecone` package) |
| `guardrails-ai-restrict-to-topic` | Ambiguous | `torch`+`transformers` unconditionally |
| `guardrails-ai-provenance-llm` | Yes, by name | `sentence-transformers` (pulls in torch transitively) despite the "LLM" name |
| `guardrails-ai-toxic-language-llm` | Yes | Only `litellm` — genuinely clean |

Only one came back clean. Given that, **every check here is a hand-written custom validator**,
registered against the real `guardrails-ai` framework (not a DIY-outside-the-library workaround —
this is the plan's documented fallback path, exercised because it turned out to be necessary, not
just because it was safer to assume).

## Input guard — `QuestionSafety` (validated on the *condensed* standalone question — see [[01-architecture]] for why)

One `ChatGroq` call (not one call per check) checks all three at once: prompt injection,
off-topic (against the per-video topic label), and profanity. Returns the first matching
`FailResult`; `PassResult()` if clean.

## Output guard — `AnswerSafety` (validated on the complete generated answer)

One `ChatGroq` call checks groundedness (is the answer supported by the retrieved context?) and
toxicity. **Runs after the answer has already streamed to the client** — it cannot un-send tokens
already shown, so a failure surfaces as a non-blocking `data-warning` flag attached to the message
(`components/ChatPanel.tsx`) rather than preventing display. The input guard, by contrast, runs
before generation and genuinely blocks. This asymmetry was a deliberate tradeoff, not an
oversight: buffering the entire answer before ever streaming it would have defeated the streaming
UX built in earlier phases for a check whose failure mode (an ungrounded or mildly-off answer) is
lower-severity than the input side's (a successful injection attack).

## Two real bugs this phase surfaced (both fixed, both non-obvious)

1. **Guardrails AI's own `settings.disable_tracing` flag doesn't work.** It phones home
   OpenTelemetry spans to a hardcoded AWS endpoint by default; setting `disable_tracing = True`
   still tried the network call, retrying with backoff, ~9.7s wasted per `guard.validate()` call
   before giving up (confirmed empirically, not assumed from docs). Fixed with the *standard*
   OTel SDK env var, `OTEL_SDK_DISABLED=true`, set in `rag/config.py` — imported earliest, before
   anything else in the codebase can import `guardrails`.
2. **gpt-oss-120b (a reasoning model) can spend its entire `max_tokens` budget on internal
   chain-of-thought and return literally empty `content`.** The guard classifiers' original
   `max_tokens=200` triggered this — every guard silently passed everything, including a textbook
   injection attempt, because the "classification" was an empty string that parsed to `{}`.
   `reasoning_effort="low"` fixes it (verified: reasoning-token consumption dropped from 66+ to
   ~14 on the same prompt). This turned out to be systemic, not guardrails-specific — see
   [[06-phased-rollout]]'s Phase 5 notes for where else it was found and fixed.

## Fallback principle (confirmed necessary in practice, kept for future validators)

If a *future* Hub validator turns out, on live inspection, to require a local ML model: do not
pull in the heavy dependency. Write a small custom validator using the same `ChatGroq` call
already in the stack, wrapped in `Guard().use()` — this is what actually happened for every
check in this phase, not a hypothetical.

## Failure policy

Input guard: `on_fail="exception"`, caught in `rag/chains/rag_pipeline.py`, re-raised as
`PipelineError`, surfaced as a clean SSE `error` event — fail-closed, the question never reaches
the LLM. Output guard: same `on_fail="exception"` mechanism, but caught and converted into a
non-blocking `data-warning` event instead (see the asymmetry note above).

## Per-video topic derivation

`rag/ingestion/indexing.py`'s `_generate_topic` — computed once per video at ingestion time (one
short `ChatGroq` call over the first chunk), stored redundantly on every chunk's Pinecone
metadata (Pinecone namespaces have no metadata store of their own, so there's no single place to
put a "namespace-level" field), read back via `get_video_topic`. Uses the same self-healing
schema-sentinel mechanism as the citation-timestamp and hybrid-search fixes (see
[[02-advanced-retrieval]]) — a video indexed before Phase 5 gets a topic label backfilled
automatically the next time it's queried, no manual reindex needed.

## Adversarial verification

Originally verified manually against both the local dev server and the live Vercel deployment: a
prompt-injection attempt and an off-topic question were each correctly caught and blocked with a
clean, friendly error message; a normal question passed through unaffected. Formalized in Phase 7
as `eval/test_guardrails.py` — six real-API pytest cases (`pytest eval/test_guardrails.py`) against
both validators: input guard passes a legitimate on-topic question and blocks prompt injection,
off-topic, and profanity; output guard passes a grounded answer and blocks an ungrounded one.
Lives in `eval/`, not `tests/`, since `validate()` makes a real Groq call — network-dependent
verification, not a pure unit test — and reuses the same pytest/CI shape as `eval/test_rag_metrics.py`
rather than standing up separate scaffolding, per the original Phase 5 deferral plan.

## Related specs

[[01-architecture]] · [[02-advanced-retrieval]] · [[06-phased-rollout]] · [[07-deployment-vercel]]
