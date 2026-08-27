@AGENTS.md

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A YouTube-video RAG chatbot: paste a video URL, ask questions grounded in its transcript. Next.js
(App Router, Vercel AI SDK) frontend + a Python RAG backend running as a single Vercel serverless
function, Pinecone for vector storage/embeddings/rerank, an open-weight LLM (`openai/gpt-oss-120b`)
served free via Groq (no OpenAI/Anthropic dependency anywhere in the stack), DeepEval for RAG
evaluation, and hand-written Guardrails AI validators for input/output safety.

The original version was a single-file Gradio app (`app.py`, now deleted). `specs/00-overview.md`
through `specs/07-deployment-vercel.md` are the source of truth for *why* the system is built this
way, not just what — read the relevant one before an architectural change. `specs/06-phased-rollout.md`
is the authoritative status tracker: phases 1–5 are done and deployed live on Vercel; phase 7
(hardening — pinned deps, unit tests, docs, dead-code cleanup) is done. Phase 6 (DeepEval) is
built, individually verified, and formalized (`tests/`, `eval/test_guardrails.py`), but one
complete batch run across the full golden set is still unverified — blocked, in turn, on the app's
`gpt-oss-120b` daily quota and then the eval judge's own `gpt-oss-20b` daily quota, both exhausted
by this session's own dev-time testing, not a code issue. See `specs/06-phased-rollout.md`'s
Phase 6/7 notes for the exact diagnosis.

## Commands

**Frontend** (Next.js):
```bash
npm run dev      # local dev server, http://localhost:3000
npm run build
npm run lint      # eslint; .venv/** is ignored (it contains a bundled Next.js admin build from litellm)
```

**Backend** (`rag/`, `api/chat.py`, `eval/`) — requires Python ≥3.10, specifically 3.12 locally
(installed via `uv python install 3.12`; DeepEval fails to *import*, not just run, on 3.9, and 3.12
matches Vercel's own runtime):
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt            # what actually ships to the Vercel function
pip install -r eval/requirements.txt       # + deepeval, dev/CI-only, deliberately not in the deployed bundle
```

**Evaluation** (`eval/`, imports `rag/` directly — never hits the live `/api/chat` endpoint, so
runs are deterministic against frozen transcript fixtures in `data/eval/fixtures/`):
```bash
python -m eval.run_eval             # fast suite: RAG triad (context relevancy, faithfulness, answer relevancy)
python -m eval.run_eval --full      # + contextual precision/recall + GEval correctness/completeness
deepeval test run eval/test_rag_metrics.py                          # pytest-native, fast suite
DEEPEVAL_FULL_SUITE=true deepeval test run eval/test_rag_metrics.py # + full suite
pytest eval/test_guardrails.py      # adversarial guardrail suite — real API calls, not frozen/mocked
```
Run as a module (`-m`), not a script — `eval/` imports are package-relative and `python eval/run_eval.py`
puts the wrong directory on `sys.path`.

**Unit tests** (`tests/`, Phase 7 — pure/deterministic logic only, no network, no live API calls):
```bash
python -m pytest tests/
```
Deliberately doesn't cover LLM-calling paths (guardrail classification, condense, retrieval/answer
quality) — that's what `eval/` + DeepEval score properly against a golden dataset; unit-testing
"did the LLM classify this right" would just be a flakier, unmocked version of the same thing.

## Architecture

**Request flow**: `app/page.tsx` (session/message state, `localStorage`-backed) → `ChatPanel`'s
`useChat` → `POST /api/chat.py` (FastAPI ASGI on a Vercel Python function) → `rag.chains.rag_pipeline.answer_question()`,
an async generator yielding tagged events (`status`/`sources`/`text`/`warning`/`suggestions`) →
`api/chat.py` maps each to the Vercel AI SDK's Data Stream Protocol (SSE) so the frontend can
render live status updates, streamed text, and citations without custom client-side plumbing.

**`rag/` pipeline stages**, each independently swappable/flag-gated (`rag/config.py` holds every
tunable — retrieval k, hybrid alpha, feature flags, model names):
1. `rag/ingestion/` — transcript fetch (Supadata's hosted API, not local scraping: both this dev
   sandbox and Vercel's own infra get IP-blocked by YouTube directly), segment-boundary chunking
   that preserves exact timestamps, dense + sparse embedding via Pinecone Inference, upsert into a
   per-`video_id` Pinecone namespace. `ensure_video_indexed()` is called lazily on first question
   about a video — there's no separate ingestion CLI.
2. **Self-healing schema**: `namespace_has_vectors()` checks a sample vector's metadata for
   sentinel fields (`start_ms`, `topic`, `sparse_values` presence) before treating a namespace as
   already indexed. A video indexed under an older schema version gets automatically re-indexed on
   next use rather than silently serving stale/incomplete data.
3. `rag/retrieval/` — hybrid dense+sparse search (query-side vector scaling via `hybrid_score_norm`,
   not post-hoc score blending), optional multi-query expansion with reciprocal rank fusion
   (`MULTIQUERY_ENABLED`, off by default — extra LLM call + N extra retrievals per question), optional
   hosted rerank (`RERANK_ENABLED`, on by default, fails soft on error).
4. `rag/memory/stm.py` — sliding-window short-term memory as pure functions. Stateless server-side:
   the client resends full message history each turn (`useChat` default), the backend just trims/
   formats the last `N_TURNS` for the condense-question step.
5. `rag/guardrails/guards.py` — hand-written Guardrails AI validators (`QuestionSafety`,
   `AnswerSafety`), not Guardrails Hub validators — every Hub validator covering these checks pulls
   in torch/transformers/sentence-transformers or a hardcoded OpenAI dependency on inspection, which
   doesn't fit a Vercel free-tier Python function's size/memory budget.
6. `rag/chains/rag_pipeline.py` — orchestrates all of the above. Also exposes `answer_for_eval()`, a
   separate simpler entry point used only by `eval/` that bypasses guardrails/condense/multiquery/
   suggestions, so eval measures core retrieval+generation quality in isolation.

**Reasoning-model gotcha, relevant anywhere a short/structured non-streaming call is made** (guard
classifiers, topic generation, the DeepEval judge): `openai/gpt-oss-120b`/`-20b` can burn an entire
`max_tokens` budget on internal chain-of-thought and return empty `content`. Always pair a
non-streaming call to these models with `reasoning_effort="low"` and a wide-enough `max_tokens`.

**`eval/`**: `eval/judge_model.py`'s `GroqJudgeModel(DeepEvalBaseLLM)` deliberately isn't DeepEval's
built-in `LiteLLMModel` — that forces schema-based structured output via tool-calling, which these
Groq-hosted models don't reliably honor. `generate()` takes no `schema` kwarg on purpose, so
`DeepEvalBaseLLM`'s own fallback to plain-text + JSON parsing kicks in for free. The judge model
(`gpt-oss-20b`) is deliberately different from the app's own `CHAT_MODEL` (`gpt-oss-120b`) — sound
eval practice (a model shouldn't grade its own outputs), and also a practical necessity since both
draw from the same Groq account's quota. DeepEval fires internal concurrent judge calls per metric
per chunk/claim, which blows through Groq's free-tier TPM limit even under an outer
`AsyncConfig(max_concurrent=1)`; `GroqJudgeModel` itself serializes and paces every call
(`asyncio.Semaphore(1)` + a minimum interval) since it's the one choke point that reaches all of them.

**Frontend structure**: `app/page.tsx` owns session state (up to 3 concurrent chats, each pinned to
a video, persisted in `localStorage`); `ChatPanel` owns the `useChat` instance and message
rendering (Markdown via `react-markdown`+`remark-gfm`, single highest-confidence source citation
per answer, auto-scroll); `SessionDock` is the full-width header (GitHub link, credits badge);
`VideoShowcase` is the left-panel video switcher; `FlashCards` is the right-panel auto-rotating
info panel linking to `app/about`. Styling is a single-accent restrained palette (`app/globals.css`)
— deliberately not the "funky"/multi-gradient look from an earlier iteration.

**Deployment**: one Next.js app + one Python serverless function (`api/chat.py`, `vercel.json` sets
`maxDuration: 60` and excludes `eval/tests/data/specs` from the function bundle). No server-side
session store — everything needed to continue a conversation travels in the request from the client.
