"""Shared test fixtures. Sets dummy env vars before `rag.config` (and anything importing it) is
first imported, so `rag/config.py`'s `os.environ.get(...)` calls resolve to harmless placeholders
instead of empty strings — none of these unit tests make real network calls, but several modules
read config at import or call time and would otherwise need every test to stub around missing keys.
"""
import os

os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("PINECONE_API_KEY", "test-pinecone-key")
os.environ.setdefault("SUPADATA_API_KEY", "test-supadata-key")
