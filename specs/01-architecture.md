# 01 — Architecture

## System diagram

```
 Browser (useChat)
      │  POST /api/chat  { messages: [...] }
      ▼
 Next.js app (Vercel, Node runtime)
      │  same-origin request, no relay — see "Why no Node relay" below
      ▼
 api/chat.py — FastAPI ASGI function (Vercel Python runtime)
      │
      ├─ 1. rag/memory/stm.py     — trim incoming `messages` to last N turns (pure function)
      ├─ 2. rag/chains/rag_pipeline.py — condense standalone question from (trimmed history + latest turn)
      ├─ 3. rag/guardrails/guards.py   — INPUT guard on the *condensed* question
      ├─ 4. rag/retrieval/retrievers.py — hybrid retrieve (Pinecone dense+sparse) → [multiquery] → [rerank]
      ├─ 5. rag/chains/rag_pipeline.py — build prompt(context, question), call ChatGroq (gpt-oss-120b), stream tokens
      ├─ 6. rag/guardrails/guards.py   — OUTPUT guard on the full generated answer (post-stream or buffered)
      └─ 7. emit AI SDK Data Stream Protocol SSE events (text-delta + custom status parts) back to client
      ▼
 Pinecone (namespace = video_id) ◄── rag/ingestion/{transcript,indexing}.py populates this
                                      the first time a video_id is seen
```

## Why no Node/Edge relay

Vercel Python functions stream natively; the AI SDK's Data Stream Protocol is transport-agnostic
(SSE + a header), not Node-specific. Adding a Node route that just forwards bytes from Python would
add a hop and consume part of the request lifecycle for no benefit. `api/chat.py` emits the SSE
response directly. See [[07-deployment-vercel]] for the exact protocol/header details.

## Why guardrail-after-condense, not guardrail-on-raw-input

A raw follow-up turn like "what about the second one?" has no keywords to check for
topicality/injection — it only makes sense once resolved against history. Running the input guard
on the *condensed* standalone question (step 3, after step 2) avoids false-positive off-topic
rejections on legitimate follow-ups. This ordering is a deliberate design choice, not an
implementation accident — get it backwards and multi-turn conversations break.

## Why history is client-resent, not server-stored

Vercel functions are stateless across invocations (no shared memory between requests, no
guaranteed same-instance reuse). The Vercel AI SDK's `useChat` already resends the full message
array on every request by default, so there is no server-side session store to build, secure, or
scale — `rag/memory/stm.py`'s sliding-window trim operates on exactly the array the client already
sent. This is simpler than (and a deliberate improvement over) a server-side session dict, which
would also risk leaking one user's history to another if implemented carelessly.

## Module responsibilities

| Module | Responsibility |
|---|---|
| `api/chat.py` | FastAPI ASGI entrypoint; request parsing, SSE response assembly; orchestrates calls into `rag/` but contains no RAG logic itself |
| `rag/config.py` | env vars, feature flags (`MULTIQUERY_ENABLED`, `RERANK_ENABLED`), model names, `N_TURNS` |
| `rag/ingestion/transcript.py` | `extract_video_id`, `fetch_transcript_text` (via Supadata's hosted API, not local scraping — see [[06-phased-rollout]] deviations) |
| `rag/ingestion/indexing.py` | chunk transcript, embed, upsert to Pinecone (namespace=video_id), namespace-exists check, per-video topic label |
| `rag/retrieval/retrievers.py` | Pinecone hybrid query + alpha blending, multi-query expansion, hosted rerank call |
| `rag/memory/stm.py` | sliding-window trim (pure function) |
| `rag/chains/prompts.py` | all `PromptTemplate`s |
| `rag/chains/rag_pipeline.py` | orchestrates condense → retrieve → guard → answer → guard, yields SSE events |
| `rag/guardrails/guards.py` | `build_input_guard()`, `build_output_guard()` |
| `eval/*` | DeepEval golden dataset + metric suites — imports `rag/` directly, never goes through `api/chat.py` or a live deployment |

`rag/` is imported by both `api/chat.py` (the deployed path) and `eval/*` / `tests/*` (the
dev-time path) — this is why RAG logic never lives inside `api/chat.py` itself: it must be
testable without spinning up the ASGI server or Vercel at all.

## Related specs

[[00-overview]] · [[02-advanced-retrieval]] · [[04-guardrails]] · [[05-memory-conversational-rag]] ·
[[07-deployment-vercel]]
