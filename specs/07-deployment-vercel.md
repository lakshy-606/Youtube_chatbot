# 07 — Deployment (Vercel)

## Why Vercel + Next.js + Python, not Gradio

Gradio is built for a long-running server process with WebSocket support (its natural free home is
Hugging Face Spaces). Vercel's model is stateless serverless functions behind a CDN — a good fit
for a Next.js frontend + Python API function, a poor fit for Gradio's server model. This project
uses Next.js (Vercel AI SDK, `useChat`) for the UI and a Python (FastAPI) Vercel function for the
RAG backend, deployed together as one project.

## Hobby (free) tier limits this design is built against — verify current values before relying on them

*(Correct as of this plan's research pass, 2026; Vercel limits change without much announcement —
re-check `https://vercel.com/docs/functions/limitations` before treating these as fixed.)*

- **Function duration**: default and maximum **300 seconds** on Hobby (via Fluid Compute, default
  since April 2025) — *not* the commonly-cited legacy 10s figure. Comfortably covers a
  condense→multiquery→retrieve→rerank→answer chain of several sequential LLM/API calls.
- **Memory**: 2GB / 1 vCPU (Hobby default and max).
- **Python bundle size (uncompressed)**: 500MB — the limit that ruled out the local cross-encoder
  reranker and ML-based Guardrails validators (see [[02-advanced-retrieval]], [[04-guardrails]]).
  A 5GB "Large Functions" beta exists but was not relied on in this design.
- **`/tmp` scratch space**: writable, ~500MB.
- **Active CPU**: 4 free hours/month on Hobby (billed only for compute-active time — I/O wait like
  calling Groq/Pinecone doesn't count against it).

The real risk this design mitigates is **perceived latency, not timeouts**: several sequential
LLM/API calls before the final answer can feel slow even nowhere near 300s, hence the SSE status
events described below.

## Streaming: AI SDK Data Stream Protocol

`api/chat.py` emits SSE with `text-start`/`text-delta`/`text-end` events (plus custom data parts
for status messages like "searching transcript…"), response header
`x-vercel-ai-ui-message-stream: v1`, terminated with `data: [DONE]`. `useChat` on the client
consumes this natively — no custom client transport config needed. (A simpler `text` stream
protocol exists as a fallback for plain-text-only streaming without tool-call/data-part support;
not needed here since status events are part of the design.) Reference: Vercel's own "AI SDK
Python Streaming" template demonstrates this exact FastAPI + Next.js shape.

## Vercel project layout

Classic co-located pattern (simpler than the newer multi-"Services" model, sufficient for this
project's scale): a single Next.js project with `api/chat.py` as a Python serverless function
alongside the `app/` frontend directory. `vercel.json` sets `functions` config
(`maxDuration`, `excludeFiles` to keep the Python bundle under 500MB by excluding dev/test-only
files like `eval/` and `tests/` from the deployed function).

## Pinecone setup

1. Create a Pinecone account, Starter (free) plan.
2. Create one serverless index (`cloud="aws"`, `region="us-east-1"` — Starter is AWS
   us-east-1-only), `vector_type="dense"`, `metric="dotproduct"`, `dimension=1024` (matching
   Pinecone Inference's `llama-text-embed-v2` dense model — see [[02-advanced-retrieval]]).
3. `PINECONE_API_KEY` set as an env var (locally in `.env`, in Vercel's dashboard for deployment).

## Required environment variables

No OpenAI or Anthropic dependency anywhere in this stack (chat runs on a free, open-source model
via Groq; embeddings run through Pinecone Inference — see [[02-advanced-retrieval]]):

| Var | Used by | Notes |
|---|---|---|
| `GROQ_API_KEY` | chat completion (gpt-oss-120b, via `langchain-groq`) + guardrail LLM checks | required, free tier |
| `PINECONE_API_KEY` | vector store + dense/sparse embeddings + hosted rerank (Pinecone Inference) | required |
| `SUPADATA_API_KEY` | transcript fetching (`rag/ingestion/transcript.py`) | required, free tier (100 req/mo) — see [[06-phased-rollout]] deviations for why this replaced local scraping |

Everything else `rag/config.py` reads (retrieval `k`, hybrid alpha, feature flags, model names,
`N_TURNS`, ...) has a working default and only needs an env var set to override it — see
`.env.example` and `rag/config.py` itself for the full list. An earlier draft of this table also
listed an optional `COHERE_API_KEY` for a rerank fallback; that fallback was never actually wired
up in `rag/retrieval/retrievers.py` (Pinecone's own hosted rerank fails soft to the pre-rerank
ordering instead — see [[02-advanced-retrieval]]), so the var was removed from `.env.example` in
the Phase 7 hardening pass rather than left as a dead, misleading entry.

Set locally via `.env` (loaded by the Python function through the same `python-dotenv` pattern the
original app used) and in the Vercel dashboard's Environment Variables settings for the deployed
app — they are two separate places to configure, both required.

## Local development

```bash
vercel dev           # emulates Next.js + the Python function together
python -m pytest tests/   # pure-function unit tests — no network, no live deployment involved
deepeval test run eval/test_rag_metrics.py   # exercises rag/ directly via eval/, same no-deployment property
```

`tests/` (Phase 7) covers the deterministic, network-free logic — video ID parsing, transcript
segment parsing/error handling, chunking, hybrid score scaling, reciprocal rank fusion, the rerank
fail-soft fallback, sliding-window trimming, schema self-healing, timestamp formatting, single-
source selection — with real network calls (Groq, Pinecone, Supadata) mocked out. It deliberately
does **not** cover the LLM-calling paths (guardrail classification, condense, retrieval quality,
answer generation) — that's what `eval/` and DeepEval are for; unit-testing "does the LLM classify
this correctly" would just be a flakier, unmocked reimplementation of what DeepEval already scores
properly against a golden dataset.

## Deploying

```bash
vercel               # preview deployment
vercel --prod         # production deployment to the project's *.vercel.app URL
```

Requires an authenticated Vercel account (`vercel login`, interactive) — not something this
assistant can do on the user's behalf.

## Related specs

[[01-architecture]] · [[02-advanced-retrieval]] · [[04-guardrails]] · [[06-phased-rollout]]
