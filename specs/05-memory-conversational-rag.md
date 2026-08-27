# 05 — Memory & Conversational RAG

## Why sliding-window, not summarization or full-history

Three common STM strategies: (1) keep full history verbatim (simplest, but prompt grows unbounded
and eventually blows the context window / costs scale with conversation length), (2) summarize
older turns into a running summary (bounded size, but adds an LLM call and lossy compression), (3)
**sliding window** — keep only the last N turns verbatim, drop older ones outright (bounded size,
no extra LLM call, no compression artifacts; the tradeoff is older context is simply gone, not
summarized). This project uses (3) — explicitly requested, and the right complexity level for a
portfolio project's conversational memory story without overbuilding.

## Design

- `rag/memory/stm.py` exposes a **pure function**: `trim_history(messages: list, n_turns: int) ->
  list`. No class, no stored state, no side effects — given the same input it always returns the
  same output, which makes it trivially unit-testable (see [[06-phased-rollout]]).
- `messages` is exactly what the Vercel AI SDK's `useChat` sends in the request body — the full
  conversation so far, client-resent every turn (see [[01-architecture]] for why no server-side
  session store exists at all).
- Default `N_TURNS = 4` (8 messages: 4 user + 4 assistant) — configurable via `rag/config.py`.
  Chosen as a reasonable default for a Q&A-over-one-video use case where follow-ups rarely need to
  reference more than a couple of exchanges back; not tuned against a benchmark, documented as a
  starting point.
- Trimming happens **before** the condense-question step, so the condense LLM call only ever sees
  the windowed history, keeping that call's cost bounded regardless of how long the conversation
  has run.

## Condense-question step

Implemented as hand-rolled LCEL (`contextualize_prompt | llm | StrOutputParser()`) rather than
LangChain's `create_history_aware_retriever` helper — that helper (along with `EnsembleRetriever`/
`MultiQueryRetriever`) now lives under `langchain_classic` post-LangChain-1.0-split, and whether
`langchain.retrievers` still re-exports it wasn't confirmed at plan time. Hand-rolling this one
step sidesteps that import-path risk entirely and is arguably more interview-explainable anyway —
it's a two-line LCEL chain, not a framework black box.

**Condense prompt (starting point, tune during implementation):**

```
Given the conversation so far and a follow-up question, rephrase the follow-up into a standalone
question that can be understood without the conversation history. If the follow-up is already
standalone, return it unchanged. Do not answer the question — only rephrase it.

Conversation history:
{chat_history}

Follow-up question: {question}
Standalone question:
```

## Interaction with guardrails

The input guard (topic/injection check) runs on the **output** of this condense step, not the raw
follow-up turn — see [[01-architecture]]'s "Why guardrail-after-condense" section for the failure
mode this avoids.

## Related specs

[[01-architecture]] · [[04-guardrails]] · [[06-phased-rollout]]
