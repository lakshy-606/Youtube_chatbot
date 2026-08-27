"""Env/config for the rag/ package. See specs/07-deployment-vercel.md for how these get set
locally (.env) vs. on Vercel (dashboard env vars)."""
import os

from dotenv import load_dotenv

load_dotenv()

# Must be set before `guardrails` is imported anywhere (rag/config.py is imported early by
# virtually every other module, so this is the safest place). Guardrails AI phones home
# OpenTelemetry spans to a hardcoded AWS endpoint by default; its own `settings.disable_tracing`
# flag does NOT actually stop this — verified empirically (~9.7s wasted per guard.validate() call
# on retries before giving up). This standard OTel SDK env var does work. See
# rag/guardrails/guards.py for the full writeup.
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

# --- LLM: an open-source model (OpenAI's open-weight gpt-oss-120b, Apache 2.0) served free via
# Groq's hosted inference — no OpenAI-the-API-provider/Anthropic dependency in this stack. See
# specs/02-advanced-retrieval.md for why. Model choice verified live against this account's
# actual available models (GET /v1/models) rather than assumed — Groq's lineup shifts over time
# and "llama-3.3-70b-versatile" (an earlier candidate) came back 404/model_not_found.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "openai/gpt-oss-120b")
CHAT_TEMPERATURE = float(os.environ.get("CHAT_TEMPERATURE", "0.4"))

# --- Transcript fetching (Supadata, hosted — see rag/ingestion/transcript.py for why) ---
SUPADATA_API_KEY = os.environ.get("SUPADATA_API_KEY", "")

# --- Pinecone (vector store + embeddings + rerank, all via Pinecone Inference) ---
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME = os.environ.get("PINECONE_INDEX_NAME", "youtube-chatbot")
PINECONE_CLOUD = os.environ.get("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.environ.get("PINECONE_REGION", "us-east-1")  # Starter tier is AWS us-east-1 only
EMBED_MODEL = "llama-text-embed-v2"
EMBED_DIMENSION = 1024
SPARSE_EMBED_MODEL = "pinecone-sparse-english-v0"
# bge-reranker-v2-m3 specifically is the free-tier rerank model on Starter (500 req/mo included);
# the other two Pinecone-hosted rerank models (pinecone-rerank-v0, cohere-rerank-v3.5) are paid
# only — verified live against Pinecone's current pricing page, not assumed.
RERANK_MODEL = "bge-reranker-v2-m3"

# --- Retrieval ---
TOP_K = int(os.environ.get("TOP_K", "8"))
# Hybrid dense/sparse blend weight (specs/02-advanced-retrieval.md): 1.0 = dense-only,
# 0.0 = sparse-only. 0.5 is Pinecone's own "balanced" starting point.
HYBRID_ALPHA = float(os.environ.get("HYBRID_ALPHA", "0.5"))
# How many candidates to fetch before reranking trims to TOP_K — reranking only helps if it has
# more than TOP_K candidates to choose from.
RETRIEVE_K = int(os.environ.get("RETRIEVE_K", "20"))
MULTIQUERY_COUNT = int(os.environ.get("MULTIQUERY_COUNT", "3"))

# --- Chunking (kept from the original app's defaults — see specs/02-advanced-retrieval.md) ---
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# --- Memory — wired up starting Phase 3 (specs/05-memory-conversational-rag.md) ---
N_TURNS = int(os.environ.get("N_TURNS", "4"))

# --- Feature flags (Phase 4, specs/02-advanced-retrieval.md) ---
# Multi-query stays opt-in by default: it's a real extra LLM call + N extra retrievals per
# question, a latency/cost tradeoff a demo deployment shouldn't pay by default. Rerank defaults
# on: it's one cheap hosted call, well within the free 500/mo quota at this app's scale, and
# strictly improves ranking quality.
MULTIQUERY_ENABLED = os.environ.get("MULTIQUERY_ENABLED", "false").lower() == "true"
RERANK_ENABLED = os.environ.get("RERANK_ENABLED", "true").lower() == "true"
