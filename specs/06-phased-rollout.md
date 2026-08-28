# 06 — Phased Rollout

Each phase lands independently runnable/demoable. Claude implements each phase and hands back for
review; the user runs/reviews rather than co-writing (see project decision log in the plan this
spec set originated from).

| # | Status | Phase | Ships | Exit criteria |
|---|---|---|---|---|
| 1 | ✅ done | Specs + scaffold + deploy proof | This `specs/` directory; Next.js app with `useChat` wired to a trivial echo; `api/chat.py` FastAPI stub emitting a hand-rolled Data Stream Protocol response; `vercel.json` | A live Vercel URL streams a trivial echo response end-to-end in a real browser |
| 2 | ✅ done | Core RAG pipeline | Ingestion (transcript fetch, chunk, embed, upsert to Pinecone by `video_id` namespace); single dense-retrieval + answer chain wired into `api/chat.py` | Asking a real question about a real video streams a real, grounded answer on the live deployment |
| 3 | ✅ done | Sliding-window STM / conversational RAG + multi-session UI | `rag/memory/stm.py`, condense-question step; **plus** (added mid-phase, see deviations) a multi-session sidebar UI: up to 3 concurrent chats, each pinned to a video with a live-fetched title/thumbnail, persisted client-side in `localStorage` | A follow-up question with pronouns ("what about that?") resolves correctly against the last few turns; the sidebar switches between up to 3 independent chats without losing history |
| 4 | ✅ done | Advanced retrieval | Pinecone hybrid (dotproduct + sparse + alpha-norm), multi-query expansion, hosted rerank — each behind a config flag; SSE status events | Toggling each flag measurably changes retrieved-context quality; status events render in the UI during multi-step turns |
| 5 | ✅ done | Guardrails AI | LLM-based input/output validators wired into the pipeline | The adversarial test set from [[04-guardrails]] passes: injection, off-topic, and unanswerable questions are each caught |
| 6 | ⚠️ built, blocked on quota | DeepEval harness | Golden dataset + fast triad suite + full suite | `deepeval test run eval/test_rag_metrics.py` runs deterministically against frozen fixtures and reports all seven metrics from [[00-overview]] |
| 7 | ⚠️ done except the Phase 6 batch run | Hardening | Pinned `requirements.txt`/`package.json`, `.env.example` cleanup, `tests/` unit suite (new), formal adversarial guardrail suite (`eval/test_guardrails.py`, new), updated `CLAUDE.md`/README, dead-code cleanup | Live Vercel URL reachable ✅, local `pytest` (49 tests) green ✅, adversarial guardrail suite (6 tests) green ✅ — `deepeval test run`/`python -m eval.run_eval` still blocked, see Phase 6/7 notes |

**Phase 6 notes:**
- **Local dev Python bumped 3.9 → 3.12.** `deepeval` (4.2.0) doesn't just fail a `requires_python`
  check on 3.9, it fails to *import* — its own source uses `X | Y` union syntax at module level.
  Installed Python 3.12 via `uv python install 3.12` (uv itself installed user-space, no sudo) and
  rebuilt `.venv` on it. This also happens to make local dev match Vercel's actual Python runtime
  (3.12+) more closely than 3.9 ever did — a genuine improvement, not just a workaround.
- **Golden dataset is hand-curated, not `Synthesizer`-generated.** The `Synthesizer`'s context-
  construction step needs its own embedding model (`ContextConstructionConfig.embedder`), which
  also defaults to OpenAI — wiring a second custom DeepEval model wrapper just for one-time
  dataset generation wasn't worth it for a set small enough (16 examples, 2 videos) that hand-
  curation gives more deliberate coverage (a golden specifically designed to test the "I don't
  know" faithfulness path, one specifically multi-part for completeness, etc.).
- **DeepEval's built-in `LiteLLMModel` (which would have been the obvious "just use Groq" path)
  doesn't work with this app's model.** It forces schema-based structured output via tool-calling;
  `openai/gpt-oss-120b` via Groq doesn't reliably comply with a forced `tool_choice` — confirmed
  empirically (`litellm.exceptions.BadRequestError: ... Tool choice is required, but model did
  not call a tool`). Fixed by writing a custom `DeepEvalBaseLLM` subclass (`eval/judge_model.py`)
  whose `generate()` takes no `schema` param — `DeepEvalBaseLLM`'s own default
  `generate_with_schema()` catches the resulting `TypeError` and falls back to plain-text +
  DeepEval's own `trimAndLoadJson` parsing, sidestepping the incompatibility entirely.
- **Real, unresolved-by-code constraint: this account's `gpt-oss-120b` free-tier daily quota
  (200,000 tokens/day) is exhausted**, entirely from this session's own cumulative testing across
  every phase (the app's `CHAT_MODEL` and the eval judge both defaulted to the same model/key).
  Diagnosed in stages, each a real fix, not a workaround for the same bug:
  1. Default concurrency (`AsyncConfig(max_concurrent=20)`) blew through the **per-minute** (TPM)
     limit immediately — several of DeepEval's own metrics fire an internal `asyncio.gather`
     burst of one judge call *per retrieved chunk/claim*, which the outer `max_concurrent` setting
     doesn't reach (it only throttles across test cases). Fixed with an instance-level
     `asyncio.Semaphore(1)` + real pacing delay *inside* `GroqJudgeModel` itself — the one place
     every call funnels through regardless of caller concurrency.
  2. That serialization made individual test cases slower than DeepEval's internal per-task
     deadline tolerates (`TimeoutError`, not a rate-limit error). Fixed with
     `DEEPEVAL_DISABLE_TIMEOUTS=1` (set in `eval/__init__.py`) — appropriate here since the
     pacing is deliberate, not a hang.
  3. With both fixed, hit the **per-day** (TPD) limit directly — a harder wall than TPM, not
     fixable by pacing since it's cumulative over 24h, not per-minute. Switched the eval judge to
     `openai/gpt-oss-20b` (`eval/metrics.py`) — a separate quota bucket, and arguably better eval
     practice anyway (a model judging its own outputs is a bias risk). This didn't fully resolve
     it: `answer_for_eval` (the pipeline being evaluated) still calls the app's own
     `CHAT_MODEL` (gpt-oss-120b) to generate each test case's `actual_output`, and *that* usage —
     from this session's extensive testing of the live app itself — is what actually exhausted
     the quota.
  - **Status as a result**: every individual piece has been verified working end-to-end with real
    API calls — `answer_for_eval` producing correct grounded answers, the fast-suite metrics
    scoring a real test case correctly with sensible reasoning (including GEval correctly
    penalizing a vague-criteria test on ad hoc content, motivating the `evaluation_steps` design),
    the judge model avoiding the tool-calling incompatibility. What has **not** been verified is a
    complete clean run across the full 16-example golden set — every attempt was blocked by the
    account's exhausted daily quota, which needs real time (rolling 24h window) to recover, not
    another code fix. Whoever picks this up next: re-run `python -m eval.run_eval` once quota has
    recovered (or against a fresh Groq key) for the first real full-suite report.
  - **Update, Phase 7**: `gpt-oss-120b`'s quota recovered and a real fast-suite run was attempted
    again — this time it got much further (the pipeline itself ran cleanly against all 16 goldens)
    before hitting a *different* wall: the **judge model's** (`gpt-oss-20b`) own daily quota, now
    also nearly exhausted by this session's cumulative dev-time testing (`198,924/200,000 TPD`
    used at the time of the error). Diagnosing that surfaced a real bug, now fixed: Groq's
    rate-limit error states longer waits as `"try again in 4m19.2s"` (minutes+seconds), but
    `eval/judge_model.py`'s retry-parsing regex only ever captured the trailing seconds group,
    silently treating a 259.2s wait as 19.2s — burning through all `_MAX_RETRIES` attempts in
    under two minutes instead of waiting out the real window, turning a recoverable rate limit
    into a hard failure. Fixed with a proper `_parse_retry_after_seconds()` helper (handles
    `h`/`m`/`s` components) and covered by `tests/test_judge_model.py`, regression-tested directly
    against the real error string hit live. With only ~1,076 tokens of headroom left on
    `gpt-oss-20b`'s TPD budget at diagnosis time — nowhere near enough for a 16-example × 3-metric
    run — further live attempts were deliberately not repeated (would just fail again immediately
    and burn more of an already-thin daily budget for no signal). **Still the one thing left
    unverified end-to-end**: whoever picks this up next, re-run `python -m eval.run_eval` once
    `gpt-oss-20b`'s TPD quota has meaningfully recovered — the retry-parsing fix means a run that
    hits a short/medium rate-limit window mid-run should now correctly wait it out instead of
    failing early.

**Phase 7 notes:**
- **Hardening scope actually shipped**: `package.json` deps pinned to exact resolved versions
  (matching `package-lock.json` — `requirements.txt` was already pinned from earlier phases);
  `.env.example`/[[07-deployment-vercel]] had a dead `COHERE_API_KEY` entry removed (documented as
  a rerank fallback that was never actually wired into `rag/retrieval/retrievers.py` — Pinecone's
  own hosted rerank already fails soft to the pre-rerank ordering); `.gitignore` fixed to cover the
  whole `.deepeval/` cache directory instead of one filename inside it; `README.md` fully rewritten
  (was still create-next-app boilerplate).
- **New `tests/` unit suite** (49 tests, `python -m pytest tests/`) — every pure/deterministic
  function in `rag/` that doesn't require an LLM call: video ID parsing, transcript segment
  parsing/error handling, chunking, hybrid score scaling, reciprocal rank fusion, the rerank
  fail-soft fallback, sliding-window trimming, schema self-healing, timestamp formatting,
  single-source selection, and the retry-parsing fix above. Real network calls (Groq, Pinecone,
  Supadata) are mocked; LLM-calling paths are deliberately left to `eval/`, per the design note in
  [[07-deployment-vercel]].
- **Real bug found and fixed while writing the rerank test**: `_rerank()`'s docstring promises a
  fail-soft fallback "if the hosted rerank call fails," but `get_pinecone_client()` was called
  *outside* the `try` block — a failure there (not just a failure inside `pc.inference.rerank()`)
  wouldn't have been caught. Low real-world likelihood (constructing the client doesn't itself
  make a network call), but the fix (move it inside the `try`) makes the code actually match what
  it already claimed to guarantee.
- **Formal adversarial guardrail suite** (`eval/test_guardrails.py`, 6 tests, real API calls) —
  closes the gap [[04-guardrails]] explicitly deferred from Phase 5: input guard passes a
  legitimate on-topic question and blocks prompt injection / off-topic / profanity; output guard
  passes a grounded answer and blocks an ungrounded one. Lives in `eval/`, not `tests/`, since
  `Guard.validate()` makes a real Groq call — verified live, all 6 passing.
- **What's left**: the one exit-criterion item not fully green is `deepeval test run`/
  `python -m eval.run_eval` itself — see the Phase 6 update above. Everything else in Phase 7's
  scope (pinning, docs, unit tests, dead-code cleanup, live-URL check, adversarial guardrail check)
  is done and verified.

**Phase 5 notes:**
- **Hub validator investigation confirmed the fallback principle was necessary, not precautionary.**
  Live PyPI inspection (`requires_dist`) of every Guardrails Hub validator that could cover input/
  output checks: `guardrails-ai-detect-prompt-injection` (rebuff-based) hardcodes an `openai`
  dependency plus an old `pinecone-client<4.0.0` pin (would conflict with this project's `pinecone`
  package); `guardrails-ai-restrict-to-topic` requires `torch`+`transformers` despite no "LLM" in
  its name; `guardrails-ai-provenance-llm` — despite being *named* LLM-based — requires
  `sentence-transformers`, which pulls in torch transitively. Only `guardrails-ai-toxic-language-llm`
  came back clean (just `litellm`). Given that, all guardrail checks are hand-written validators
  (`rag/guardrails/guards.py`) registered against the real `guardrails-ai` framework (`Guard`/
  `Validator`/`@register_validator`/`PassResult`/`FailResult` — all verified against a real
  installed-package test, not docs alone), consolidated into ONE LLM call for input checks
  (injection/off-topic/profanity) and ONE for output checks (groundedness/toxicity) rather than
  one call per check, for latency.
- **Real bug found and fixed: Guardrails AI's own `settings.disable_tracing` flag does not stop
  its telemetry.** It phones home OpenTelemetry spans to a hardcoded AWS endpoint by default;
  setting `disable_tracing = True` still triggered the network attempt, retrying with backoff,
  ~9.7s wasted per `guard.validate()` call before giving up (confirmed empirically) — with two
  guard calls per turn, that's ~19s of pure dead time on every question. Fixed with the *standard*
  OpenTelemetry SDK env var, `OTEL_SDK_DISABLED=true`, set in `rag/config.py` (imported earliest,
  before anything else can import `guardrails`) so it's guaranteed to apply regardless of import
  order elsewhere.
- **Real bug found and fixed, systemic, not guardrails-specific: gpt-oss-120b (a reasoning model)
  can spend its entire `max_tokens` budget on internal chain-of-thought and emit literally empty
  `content`.** Caught first in the guardrail classifiers (`max_tokens=200` → empty response →
  every guard silently passed everything, including a textbook prompt-injection attempt) and then
  found identically broken in `rag/ingestion/indexing.py`'s `_generate_topic` (`max_tokens=40` —
  had been silently returning `""` for every video since Phase 5 work started). Fixed by adding
  `reasoning_effort="low"` to every short/structured non-streaming call in the codebase (guard
  classifiers, topic generation, and `rag/chains/rag_pipeline.py`'s `_get_llm(streaming=False)`
  path used by condense/multi-query/suggestions) plus wider token budgets as a safety margin. The
  main streamed answer call keeps default reasoning effort, where answer quality matters most.
  This is a real interview-relevant gotcha about reasoning models generally, not a one-off fix.
- **Real bug found and fixed: `.venv/` wasn't in ESLint's ignore list.** Installing
  `guardrails-ai` pulled in `litellm`, which bundles its own pre-built Next.js admin dashboard
  *inside the installed Python package* — ESLint happily tried to lint those minified JS bundle
  files as project source (11,800 reported problems from one file). Fixed by adding `.venv/**` to
  `eslint.config.mjs`'s `globalIgnores`.
- **Output guard runs after the answer has already streamed**, not before — it can't un-send
  tokens already shown to the user, so a failure surfaces as a `data-warning` flag attached to the
  message (`components/ChatPanel.tsx`'s `GuardWarning`) rather than blocking. The input guard, by
  contrast, runs before any generation and genuinely blocks (raises `PipelineError`, same path as
  any other user-facing error). See [[04-guardrails]] for why this asymmetry was accepted rather
  than buffering the whole answer before ever streaming it.
- **Per-video topic label** (`rag/ingestion/indexing.py`'s `_generate_topic`) is computed once at
  ingestion time and stored redundantly on every chunk's Pinecone metadata (namespaces have no
  metadata store of their own), read back via `get_video_topic` for the input guard's off-topic
  check. Same self-healing schema-sentinel mechanism as the citation-timestamp and hybrid-search
  fixes — `_SCHEMA_SENTINEL_FIELDS` now includes `"topic"`, so any video indexed before Phase 5
  gets a topic label backfilled automatically on next use.

**Phase 4 notes:**
- **Hybrid alpha-weighting confirmed empirically**: Pinecone's `hybrid_score_norm` scales the
  *query-side* dense/sparse vectors before a single `index.query(vector=, sparse_vector=)` call —
  verified live against Pinecone's docs before implementing (`rag/retrieval/retrievers.py`), not
  assumed. `HYBRID_ALPHA` defaults to 0.5 (balanced).
- **Rerank model**: `bge-reranker-v2-m3` specifically — the only Pinecone-hosted rerank model
  included free on Starter (500 req/mo); `pinecone-rerank-v0`/`cohere-rerank-v3.5` are paid-only.
  Verified live against Pinecone's pricing page. `RERANK_ENABLED` defaults **on** (cheap, quality
  positive, ample free quota at this app's scale); `MULTIQUERY_ENABLED` defaults **off** (a real
  extra LLM call + N extra retrievals per question — a latency/cost tradeoff left opt-in).
  `_rerank()` fails soft (falls back to unranked results) if the call errors — quota exhaustion
  should never break an answer.
- **Self-heal check extended**: `namespace_has_vectors` (already checking for `start_ms`) now also
  requires `sparse_values` on the sample vector — a video indexed before hybrid search existed
  gets automatically re-indexed with sparse embeddings added, same self-healing mechanism as the
  earlier citation-timestamp fix, no manual cache-clearing needed.
- **Status events**: `answer_question` now yields `{"type": "status", ...}` before condensing (if
  there's history) and before retrieval — mapped to transient `data-status` SSE parts (delivered
  via `useChat`'s `onData`, never persisted into message history). This required moving `Chat`
  instance creation from `app/page.tsx` into `components/ChatPanel.tsx` itself, since `onData` is
  only settable at `Chat` construction time, not on `useChat({chat})` when passing an existing
  instance — same `react-hooks/set-state-in-effect` lint rule as before also applied here (status
  reset moved into the `ask()` event handler, not an effect).

**Deviations from the original plan, worth knowing before touching Phase 5+:**
- **Header polish + GitHub link + dual thumbnail nav arrows.** `SessionDock` got a brand mark
  (small icon + "YouTube RAG" wordmark, left), a divider, and a subtle accent-tinted 1px bottom
  edge (via an `after:` pseudo-element gradient) instead of the plain neutral border. Added
  `components/GithubBadge.tsx` linking `github.com/lakshy-606/Youtube_chatbot` — icon-only, no
  label. Note: the installed `lucide-react` version has **dropped brand/logo icons** (no `Github`
  export, generic icons only) — the GitHub mark is a small inline SVG here, not a lucide import;
  re-check this if adding other brand icons later. `components/VideoShowcase.tsx`'s single "next"
  arrow became a pair — left = previous, right = next (`step(-1|1)`), fixing the earlier
  left-arrow-labeled-"next" oddity now that both directions exist.
- **Header made full-width.** Follow-up correction to the entry below: "detached" alone wasn't
  enough — `SessionDock` is now a true top bar spanning the full viewport width (`app/page.tsx`
  moved it outside the centered `max-w-3xl` stage, flush at the top, no longer rounded on all
  sides), with `VideoShowcase`/chat card/`FlashCards` positioned in the remaining space below it.
- **Header detached from the chat window; attribution badge added; showcase gets session nav.**
  `app/page.tsx` restructured so `SessionDock` and the chat card are two separate floating panels
  (each its own `glass-panel`, stacked with a gap) instead of one stacked card — `SessionDock`
  itself now carries its own rounded/shadowed container. `components/CreditsBadge.tsx` added: a
  small "!" circle at the far right of the header, hover reveals "Created by Lakshya Singh",
  click opens `https://www.linkedin.com/in/lakshya-singh596/`. `components/VideoShowcase.tsx` now
  takes `sessions`/`activeId`/`onSelect` (not just the single active session) and overlays a
  chevron button on the left edge of its thumbnail to cycle to the next open chat, so switching
  sessions is reachable from the showcase panel too, not only the header dock.
- **Left-side empty space filled + citations reduced to one.** `components/VideoShowcase.tsx`
  added (mirrors `FlashCards`' positioning on the opposite side, `xl`+ only): the active session's
  thumbnail (rectangular/16:9, not circular — a circular crop loses most of a real thumbnail's
  content at this size) + title in a glass panel. `ChatPanel`'s own in-panel video header was
  cut down to a single-line 28px-thumbnail bar now that the full card lives in the showcase (kept
  only so context survives below `xl`, where the showcase is hidden). `_build_sources` in
  `rag/chains/rag_pipeline.py` now returns just the single highest-`score` chunk instead of every
  deduped retrieved timestamp — one confident citation instead of several approximate ones.
- **Real bug: citations always showed 0:00 for videos indexed before citations existed.** Root
  cause: `namespace_has_vectors` only checked "does this namespace have any vectors," so a video
  indexed under the pre-citation schema (metadata without `start_ms`) looked permanently
  "already indexed" and never picked up the new field — `retrieve()`'s `.get("start_ms", 0)`
  default silently papered over the missing key instead of erroring, so it was a hard bug to spot
  from behavior alone. Fixed in `rag/ingestion/indexing.py`: `namespace_has_vectors` now fetches
  one sample vector and checks the current schema's sentinel field (`start_ms`) is actually
  present, self-healing (upsert overwrites by deterministic vector ID) rather than requiring
  manual cache-clearing. Verified against a real previously-stale namespace both locally and on
  the live deployment — timestamps went from all-zero to real, distinct values.
- **Real bug: chat didn't auto-scroll.** `components/ChatPanel.tsx` now has a bottom sentinel
  `div` + `scrollIntoView` in a `useEffect` keyed on `[messages, status]`, so it tracks a response
  as it's still streaming in, not just once it finishes.
- **Design direction reversed: dropped the "funky"/playful look for a restrained, professional
  one** — user feedback was that the multi-orb ambient background, shifting rainbow card border,
  two-color accent gradients on every button/heading, and emoji icons read as childish rather than
  professional. Reworked: `app/globals.css` now defines one accent color (`--accent`, indigo-blue)
  instead of a two-hue gradient pair; `components/AmbientBackground.tsx` is a single slow,
  low-opacity glow instead of four bouncing colored orbs; the `.funky-border` shifting-gradient
  class is gone; buttons are solid `bg-accent` (not gradient-filled); every emoji icon (in
  `lib/facts.ts`, `lib/architecture.ts`, source citation chips) was replaced with a `lucide-react`
  icon; `TiltCard` hover-tilt angles were reduced (10° default → 4-5° where used) for a subtler
  effect. The underlying features (flash cards, About page, parallax, session dock) are unchanged
  in substance — only the visual language changed.
- **Rotating "about this app" flash cards + a `/about` page added** — `components/FlashCards.tsx`
  (right-side widget, hidden below `xl` breakpoint, auto-advances every 30s through `lib/facts.ts`,
  clicking navigates to `/about`) and `app/about/page.tsx` (server component for metadata) +
  `components/AboutContent.tsx` (the actual client-rendered content: a mouse-parallax hero via the
  new `components/ParallaxScene.tsx` + `ParallaxLayer`, then a component-by-component architecture
  breakdown from `lib/architecture.ts`, reusing `TiltCard` per card). Both `lib/facts.ts` and
  `lib/architecture.ts` are deliberately honest about build status — a separate "on the roadmap"
  section lists Phase 4-6 (hybrid retrieval, guardrails, DeepEval) as planned, not live, so the
  app never claims a feature it doesn't actually have yet.
- **Sidebar removed in favor of a single-canvas floating layout** — `components/Sidebar.tsx`
  deleted; replaced by `components/AmbientBackground.tsx` (fixed, full-viewport, CSS-only drifting
  blurred-gradient orbs behind everything — no WebGL, consistent with the earlier TiltCard
  decision) and `components/SessionDock.tsx` (a slim horizontal strip of circular thumbnail tabs
  at the top of one centered glass panel, replacing the old fixed side panel). The 3-session
  cap/switch/persist behavior from the earlier sidebar is unchanged in substance — only the visual
  container changed, not the underlying `lib/sessions.ts` model. `app/page.tsx` now renders one
  `max-w-3xl` glass-panel "floating card" (`SessionDock` + `ChatPanel` stacked inside it) centered
  over the ambient background, instead of a two-column `[Sidebar][main]` layout.
- **UX review round (post-Phase-3, pre-Phase-4)** — user reviewed the deployed app and flagged 7
  issues; all addressed before moving on:
  1. Markdown wasn't rendering (`**bold**` shown literally) → `react-markdown` + `remark-gfm` +
     `@tailwindcss/typography` added; `ANSWER_PROMPT` now explicitly asks for Markdown structure.
  2. Wall-of-text answers → same prompt change asks for short paragraphs/bullets over one dense block.
  3. No source grounding → **timestamp citations built** (see [[02-advanced-retrieval]]'s chunking
     section) — retrieved chunks' timestamps become clickable `youtu.be/<id>?t=<seconds>` chips under
     each answer, delivered as a `data-sources` stream part (see [[01-architecture]]).
  4. Chat layout felt unbalanced (bubbles floating at full-panel-width edges) → messages/input now
     sit in a centered `max-w-3xl` column instead of stretching the full chat panel width.
  5. Unexplained floating bottom-corner icon → likely Vercel's account-holder-only Toolbar, not
     app code; `devIndicators: false` set in `next.config.ts` to rule out Next's own dev badge as
     the source (real fix, if it persists, is on the Vercel-account side, not this codebase).
  6. "2/3 chats" indicator too subtle → `components/Sidebar.tsx` now shows a small progress bar,
     turns amber at the cap with an explicit "close one to start a new chat" message.
  7. Empty space below short answers → **follow-up suggestions built**: one extra non-streamed LLM
     call after the answer (`_generate_suggestions` in `rag/chains/rag_pipeline.py`, grounded in
     the same retrieved context so suggestions are answerable, not generic filler), delivered as a
     `data-suggestions` stream part; clicking a suggestion pill sends it as the next question.
     Failures here are swallowed (best-effort) — a bad suggestions call must never break the
     answer that already streamed successfully.
  Backend consequence: `answer_question` changed from `AsyncIterator[str]` to
  `AsyncIterator[dict]` (tagged `sources`/`text`/`suggestions` events) so `api/chat.py` can map
  each to the right Data Stream Protocol event type — see that module's docstring.
- **Multi-session UI added, beyond the original plan's scope** — user requested a ChatGPT/Claude-style
  sidebar mid-Phase-3: up to `MAX_SESSIONS = 3` concurrent chats, each pinned to one video, switchable
  without losing history, capped (not auto-evicted — creating a 4th is blocked until one is closed).
  Implementation: `lib/sessions.ts` (session list + per-session messages in `localStorage`, no
  server-side/account storage — matches "temporary" framing), `app/api/video-meta/route.ts` (Next.js
  Node route, YouTube oEmbed lookup for title + `img.youtube.com` thumbnail, avoids CORS/API-key
  issues), `components/TiltCard.tsx` (CSS-only 3D hover-tilt, no WebGL dependency — user chose this
  over a Three.js scene), `components/{Sidebar,ChatPanel,NewChatDialog}.tsx`, `app/page.tsx`
  (orchestrates session state, video metadata, and per-session `Chat` instances from `@ai-sdk/react`).
  Each active session's `Chat` instance is **derived via `useMemo`, not cached in a ref** — recreated
  from `localStorage` on every session switch rather than kept alive in memory. This was a deliberate
  fix for two real React strict-mode/lint errors (`react-hooks/set-state-in-effect`,
  ref-access-during-render) that a naive ref-Map cache triggered; since `localStorage` is the actual
  source of truth (persisted on every message change), recreating the instance is equivalent in
  practice, just simpler and lint-clean. Tradeoff: switching away from a session mid-stream and back
  loses that in-flight (not-yet-persisted) delta — accepted as a non-issue at this app's scale.
- **`hydrated` (client-mount) flag uses `useSyncExternalStore`, not `useState`+`useEffect`** — same
  lint rule as above; this is React's own documented pattern for a hydration-safe "are we on the
  client yet" check (differing server/client snapshots, no-op subscribe), not a workaround.
- **LLM provider**: not Anthropic (as originally planned) — switched to a free, open-source model
  (`openai/gpt-oss-120b`, Apache 2.0) served via Groq, per user direction. No OpenAI/Anthropic key
  exists anywhere in this stack. See [[02-advanced-retrieval]].
- **Model ID is live-verified, not assumed**: Groq's available models shift; `llama-3.3-70b-versatile`
  (an earlier candidate) 404'd on this account. Before changing `CHAT_MODEL`, check
  `GET https://api.groq.com/openai/v1/models` against the real key rather than trusting docs/specs.
- **Transcript fetching: switched from local scraping (`youtube_transcript_api`) to Supadata's
  hosted API** (`rag/ingestion/transcript.py`), resolving a real investigation, not a
  precautionary swap:
  1. YouTube's IP-based anti-bot blocking (`IpBlocked`) was confirmed to hit *both* this dev
     sandbox and Vercel's own deployed serverless IP pool — an earlier note here claimed Vercel
     was clear based on one successful request against an already-cached video; that was wrong,
     it was luck. A second, previously-uncached video (`cTQ3Ko9ZKg8`) got genuinely `IpBlocked`
     from the live deployment.
  2. Along the way, fixed a related bug: `rag/chains/rag_pipeline.py` was re-fetching the
     transcript on *every* question, even for already-indexed videos — `ensure_video_indexed`
     now takes a lazy `get_transcript_text` callable so an already-cached `video_id` never
     touches the transcript source again (see `rag/ingestion/indexing.py`). Reduced exposure, but
     didn't eliminate it for first-time videos.
  3. Webshare's free-tier proxies (datacenter-class) were tested directly and also blocked — a
     different symptom (Google's CAPTCHA/rate-limit challenge, HTTP 429) but the same underlying
     cause: datacenter-class IPs are what gets targeted, proxied or not.
  4. Residential proxies would have worked but cost money (~$3.50/GB); Supadata was chosen
     instead — a hosted service built specifically for this problem, genuinely free (100
     req/month, no card), and since `ensure_video_indexed` only calls it for first-time videos,
     that quota comfortably covers demo/portfolio-scale usage. `SUPADATA_API_KEY` required — see
     [[07-deployment-vercel]].

## Sequencing rationale

- **Deploy proof before RAG complexity (1 before 2)** — the Vercel/Next.js/Python streaming stack
  is the newest, least-proven part of this project. Proving it works with a trivial echo isolates
  platform risk from RAG-logic risk; debugging both at once would be much harder to diagnose.
- **Memory before advanced retrieval (3 before 4)** — the conversational (condense-question) step
  changes the pipeline's shape (an extra LLM call up front, a different input contract). Better to
  absorb that shape change while retrieval is still simple, then layer hybrid/multiquery/rerank
  onto a settled pipeline.
- **Advanced retrieval before eval (4 before 6)** — evaluating the naive single-retriever baseline
  wouldn't be very informative; eval is most useful once there's a real pipeline (with reranking,
  hybrid search) to actually measure and catch regressions in.
- **Eval harness measures the ungated pipeline, regardless of build order** — guardrails ship in
  Phase 5, the eval harness in Phase 6, but `eval/*` calls `rag/chains/rag_pipeline.py`'s
  retrieval+generation directly and does not route through `rag/guardrails/guards.py`. A blocked
  golden-set question would otherwise fail DeepEval's metrics for the wrong reason (guardrail
  rejection, not retrieval/answer quality) — guardrail behavior is verified separately by the
  adversarial test set in [[04-guardrails]], not conflated with the quality metrics in
  [[03-evaluation-deepeval]].

## Related specs

[[00-overview]] · [[01-architecture]] · [[07-deployment-vercel]]
