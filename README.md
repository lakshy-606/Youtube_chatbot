# YouTube RAG Chatbot

Paste a YouTube video URL, ask questions about it, get streamed answers grounded in the actual
transcript — with timestamp citations that link back to the exact moment in the video.

**Live**: https://youtube-rag-chatbot.vercel.app

Built as a from-scratch rewrite of a single-file Gradio prototype into a production-shaped,
interview-ready RAG system: conversational memory, hybrid retrieval, reranking, LLM guardrails,
and a DeepEval evaluation harness — deployed on Vercel's free tier, with **no OpenAI or Anthropic
dependency anywhere in the stack**.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js 16 (App Router) + Vercel AI SDK (`useChat`) | Streaming chat UI, SSE handled for free |
| Backend | FastAPI on a Vercel Python serverless function | One deployable project, no separate server |
| LLM | `openai/gpt-oss-120b`, served free via Groq | Open-weight model, zero-cost inference, no OpenAI/Anthropic key |
| Vector store | Pinecone (serverless, hybrid dense+sparse) | Managed, generous free tier, hosted embeddings + rerank |
| Transcripts | Supadata hosted API | YouTube blocks scraping from cloud IPs (confirmed against both this dev box and Vercel's own infra) |
| Guardrails | Guardrails AI, hand-written validators | Every Hub validator for these checks pulled in torch/transformers or a hardcoded OpenAI dep |
| Evaluation | DeepEval | RAG triad + precision/recall + G-Eval correctness/completeness |

## Features

- **Conversational RAG** — sliding-window short-term memory rephrases follow-ups ("what about the
  second one?") into standalone questions before retrieval, without any server-side session store.
- **Hybrid retrieval** — dense + sparse search via query-side vector scaling (Pinecone's documented
  `hybrid_score_norm` pattern), plus optional multi-query expansion (RAG-Fusion) and hosted
  reranking, each independently flag-gated.
- **Timestamp citations** — transcripts are chunked at real segment boundaries (not arbitrary
  character cuts), so every citation is an exact `?t=` link, never interpolated.
- **Self-healing vector schema** — a video indexed under an older metadata schema is detected via
  a sentinel-field check on a sample vector and automatically re-indexed, instead of silently
  serving stale data forever.
- **LLM guardrails** — one input-guard call catches prompt injection, off-topic questions, and
  profanity; one output-guard call flags ungrounded or toxic answers after they've streamed.
- **RAG evaluation** — a hand-curated 16-example golden dataset scored against a custom
  `DeepEvalBaseLLM` judge (a second, separate Groq model from the one the app itself uses) across
  seven metrics: context relevancy, faithfulness, answer relevancy (the RAG triad), contextual
  precision/recall, and G-Eval correctness/completeness.

See `specs/00-overview.md` for the full goals/non-goals and an interview-oriented glossary of every
technique used, and `specs/06-phased-rollout.md` for what's shipped vs. pending.

## Running locally

**Frontend:**
```bash
npm install
npm run dev      # http://localhost:3000
```

**Backend** (requires Python ≥3.10, developed against 3.12 — `deepeval` fails to *import* on 3.9):
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # what actually ships to the Vercel function
pip install -r eval/requirements.txt   # + deepeval, pytest — dev/CI-only
cp .env.example .env                   # fill in GROQ_API_KEY, PINECONE_API_KEY, SUPADATA_API_KEY
```

**Full stack together:**
```bash
vercel dev
```

**Tests and evaluation:**
```bash
python -m pytest tests/                     # pure-function unit tests, no network
pytest eval/test_guardrails.py              # adversarial guardrail suite — real API calls
python -m eval.run_eval                     # DeepEval RAG triad against frozen fixtures
python -m eval.run_eval --full              # + precision/recall + G-Eval correctness/completeness
```

See `CLAUDE.md` for the full command reference and `specs/07-deployment-vercel.md` for Vercel
project setup and environment variable configuration.

## Project structure

```
app/            Next.js pages (chat UI, /about)
components/     React components (chat panel, video switcher, flashcards, header)
lib/            Frontend-side pure helpers (session storage, video metadata, static content)
api/chat.py     FastAPI entrypoint — the one deployed Python serverless function
rag/            The RAG pipeline: ingestion, retrieval, memory, guardrails, orchestration
eval/           DeepEval harness — imports rag/ directly, never hits the live API
tests/          Unit tests for rag/'s pure/deterministic logic
data/eval/      Frozen transcript fixtures + the hand-curated golden dataset
specs/          Design docs — the source of truth for *why*, not just what
```

## Design notes

Every non-obvious decision in this codebase — why Supadata instead of scraping, why a custom
DeepEval judge model instead of the built-in one, why guardrails are hand-written instead of using
Guardrails Hub validators, why the eval judge model differs from the app's own chat model, and
more — is documented inline where the decision lives, and indexed in `specs/`. Start with
`specs/00-overview.md`.
