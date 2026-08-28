# 02 — Advanced Retrieval

## Chunking

`rag/ingestion/indexing.py:chunk_transcript_segments` — groups Supadata's timestamped transcript
segments into ~`CHUNK_SIZE` (1000 char) chunks at segment boundaries, each tagged with `start_ms`
(the exact timestamp of its first segment), with the trailing ~`CHUNK_OVERLAP` (200 char) worth of
segments carried into the next chunk. This replaced an earlier `RecursiveCharacterTextSplitter`
approach (arbitrary character-boundary splitting on plain joined text, no timestamp) once
timestamp citations became a requirement — segment-boundary grouping is what makes an *exact*
`start_ms` per chunk possible, vs. an interpolated/approximate one. Every chunk's Pinecone metadata
carries `video_id`, `text`, and `start_ms`; `rag/chains/rag_pipeline.py` turns retrieved chunks'
`start_ms` into deduped, sorted `youtu.be/<id>?t=<seconds>` citation links shown under each answer
— see [[01-architecture]] for how these reach the client as a `data-sources` stream part.

## Vector store: Pinecone

- **No OpenAI or Anthropic dependency anywhere in this stack** — the LLM is an **open-source
  model** (OpenAI's open-weight `openai/gpt-oss-120b`, Apache 2.0 licensed) served **free** via
  Groq's hosted inference (`langchain-groq`'s `ChatGroq`; free tier, rate-limited, no self-hosting
  needed — a genuinely self-hosted model doesn't fit Vercel's stateless, GPU-less serverless
  functions any better than the local cross-encoder reranker did, so "open-source model" here
  means open-weight model + free hosted inference, not local inference). Model choice was
  verified live against the actual Groq account's available models (`GET /v1/models`), not
  assumed — an earlier candidate, `llama-3.3-70b-versatile`, came back `model_not_found` on this
  account despite being documented; Groq's model lineup shifts, so re-verify before relying on a
  specific model ID. Embeddings use **Pinecone's own hosted
  Inference models** rather than a separate embeddings provider: `llama-text-embed-v2` for dense vectors,
  `pinecone-sparse-english-v0` for sparse vectors (`pc.inference.embed(model=..., inputs=[...],
  parameters={"input_type": "passage"|"query", "truncate": "END"})`). Both are billed against the
  same free Starter-tier Inference allotment as the hosted reranker, so this is one fewer external
  vendor/API key than the original OpenAI-embeddings design, not just a substitution.
- One serverless index, `metric="dotproduct"`, `vector_type="dense"`, dimension matching
  `llama-text-embed-v2`'s output (1024) — storing both a dense vector and a sparse vector per
  record so a single index serves both dense-only and hybrid queries.
- `video_id` (already regex-constrained to `[0-9A-Za-z_-]{11}` by `extract_video_id`) is used as
  the **namespace**. One namespace per video keeps queries scoped without a metadata filter and
  matches the app's mental model directly.
- **Starter (free) tier cap: 100 namespaces per index, 5 indexes per project** (500 namespaces
  total). If the deployed app needs to support more concurrently-indexed videos than that:
  fall back to a single shared namespace with `video_id` as a **metadata filter** instead — noted
  here so it's a deliberate migration, not a surprise outage.
- Ingestion (`rag/ingestion/indexing.py`) checks whether a namespace already has vectors before
  re-embedding a video — this is the persistence/caching win a FAISS-on-disk cache would have
  given in a traditional server, achieved here through Pinecone itself since a stateless Vercel
  function can't rely on local disk surviving between invocations.

## Hybrid search — built, Phase 4

`rag/retrieval/retrievers.py`. Native Pinecone hybrid query: one `index.query()` call with both
`vector=` (dense) and `sparse_vector=` (lexical). Confirmed live against Pinecone's docs before
implementing, not assumed: alpha-weighting is applied to the **query-side vectors themselves**
before that single call (`_hybrid_score_norm` scales dense by `alpha`, sparse by `1 - alpha`) —
not a post-query blend of two separate result sets. `HYBRID_ALPHA` defaults to 0.5 (balanced),
configurable. This replaced the originally-considered in-process `BM25Retriever` over a full
document list, which wouldn't have survived a stateless function's per-invocation reset anyway.

## Query expansion (multi-query / RAG-Fusion) — built, Phase 4

`rag/chains/rag_pipeline.py:_generate_query_variants` + `rag/retrieval/retrievers.py`'s
`_reciprocal_rank_fusion`. Gated behind `MULTIQUERY_ENABLED` (default **off** — a real extra LLM
call + `MULTIQUERY_COUNT` (default 3) extra retrieval calls per question, a latency/cost tradeoff
left opt-in). When on: an LLM generates paraphrases of the condensed question, each is retrieved
independently (`RETRIEVE_K` candidates each), and results are fused by reciprocal rank (not raw
score — scores from separate query calls aren't directly comparable, ranks are).

## Reranking — built, Phase 4

**Decision: no local cross-encoder in the deployed path.** `HuggingFaceCrossEncoder` +
`sentence-transformers` pulls in a `torch` CPU wheel (~520MB compressed) that alone exceeds
Vercel's 500MB Python function bundle limit, and risks the 2GB Hobby memory ceiling once
loaded alongside the rest of the LangChain/FastAPI runtime. See [[07-deployment-vercel]] for the
exact limits this is measured against.

Instead: **Pinecone's hosted Inference rerank**, model `bge-reranker-v2-m3` specifically —
verified live against Pinecone's pricing page that this is the one rerank model included free on
Starter (500 requests/month); `pinecone-rerank-v0` and `cohere-rerank-v3.5` are paid-only.
`RERANK_ENABLED` defaults **on** (cheap, quality-positive, ample free quota at this app's scale).
`rag/retrieval/retrievers.py:_rerank` fails soft — a rerank error (quota exhaustion, transient
fault) falls back to the pre-rerank ordering rather than breaking the answer. No Cohere fallback
was implemented (soft-fail was judged sufficient); revisit if Pinecone's free quota proves too
tight in practice. The local cross-encoder approach is kept only as a documented
**offline/eval-only** technique — e.g. scoring retrieval quality in a notebook — never imported by
`api/chat.py`.

## Pipeline order

`[condense] → [multiquery fuse] → hybrid retrieve → [rerank] → prompt → stream answer`. Bracketed
steps are conditional/config-gated (condense only runs when there's history; multiquery and rerank
per their flags). Guardrails (`guard(in)`/`guard(out)`) are Phase 5, not yet wired in — see
[[04-guardrails]] for that design.

## Related specs

[[01-architecture]] · [[05-memory-conversational-rag]] · [[07-deployment-vercel]]
