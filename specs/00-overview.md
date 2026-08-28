# 00 — Overview

## Problem statement

The original app was a single-file Gradio script: single-turn Q&A over one YouTube transcript,
rebuilding an in-memory FAISS index on every question, with no memory, no safety checks, and no
way to measure answer quality. This spec set upgrades it into a portfolio-grade, interview-ready
RAG system: a Next.js chat UI on Vercel, a Python RAG backend with production-shaped retrieval,
a persistent vector store, conversational memory, LLM-safety guardrails, and a DeepEval-based
evaluation harness.

## Goals

- Real multi-turn conversational RAG (sliding-window short-term memory) over a YouTube video's
  transcript.
- Advanced retrieval beyond naive top-k similarity: hybrid (dense+sparse) search, query expansion,
  reranking.
- Input/output guardrails via Guardrails AI (prompt injection, off-topic, groundedness, toxicity).
- A DeepEval evaluation suite reporting precision, recall, faithfulness, answer relevance, the
  RAG triad, correctness, and completeness — runnable on demand, not just eyeballed.
- Deployed and reachable on Vercel's free (Hobby) tier.
- Every design decision explainable in an interview: no black-box choices, no unexplained deps.

## Non-goals

- Multi-user auth/accounts, billing, or a persistent per-user chat history across sessions
  (history lives client-side for the duration of a browser session, per `05-memory-conversational-rag.md`).
- Support for non-English transcripts (inherited limitation from the original app; documented, not
  fixed here).
- Long-term memory / cross-session personalization (only short-term, sliding-window memory is in
  scope — see glossary).
- Production-scale traffic handling — this targets Vercel Hobby's free limits, not high QPS.

## Success criteria

- A user can paste a YouTube video ID/URL, ask a question, get a streamed answer with retrieved
  context, and ask a natural follow-up question that correctly resolves pronouns/references
  against the last few turns.
- `deepeval test run eval/test_rag_metrics.py` runs against frozen fixtures and reports all seven
  metrics named in Goals.
- A prompt-injection attempt, an off-topic question, and a deliberately unanswerable question are
  each caught by a guardrail rather than silently answered.
- The app is live on a `*.vercel.app` URL, deployed on the Hobby (free) plan.

## Glossary (interview cross-reference)

- **STM (short-term memory)** — conversational memory scoped to the current session/window, as
  opposed to long-term memory (a persistent store across sessions). Here: a sliding window of the
  last N turns, not a summarized or vector-stored history.
- **Sliding-window memory** — keep only the most recent N turns (fixed count or token budget),
  dropping older ones — the simplest STM strategy, contrasted with summarization-based memory or
  full-history memory.
- **Hybrid search** — combining dense (embedding/semantic) retrieval with sparse (keyword/BM25 or
  Pinecone's sparse vectors) retrieval, fused into one ranked list — captures both semantic
  similarity and exact keyword matches.
- **Query expansion / multi-query (RAG-Fusion)** — using an LLM to generate paraphrases of the
  user's question, retrieving for each, and fusing results — increases recall by not depending on
  one exact phrasing.
- **Reranking** — a second-pass scoring model (cross-encoder or hosted rerank API) that reorders
  an initial retrieval's candidates by relevance to the query, more precise but more expensive than
  the first-pass retriever alone.
- **RAG triad** — three reference-free RAG quality metrics evaluated together: context relevance
  (did retrieval find relevant chunks?), groundedness/faithfulness (is the answer supported by the
  retrieved context?), answer relevance (does the answer address the question?). Originated with
  TruLens; implemented here via DeepEval's `ContextualRelevancyMetric` + `FaithfulnessMetric` +
  `AnswerRelevancyMetric`.
- **G-Eval** — a DeepEval metric that uses an LLM-as-judge with an explicit chain-of-thought
  rubric (`evaluation_steps`) to score free-form criteria (like "correctness" or "completeness")
  that don't reduce to a fixed formula.
- **Guardrails** — programmatic input/output validation around an LLM call (as distinct from
  prompting alone) — here via Guardrails AI's `Guard().use(validator, on_fail=...)` pattern.

## Related specs

[[01-architecture]] · [[02-advanced-retrieval]] · [[03-evaluation-deepeval]] · [[04-guardrails]] ·
[[05-memory-conversational-rag]] · [[06-phased-rollout]] · [[07-deployment-vercel]]
