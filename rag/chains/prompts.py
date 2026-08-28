"""PromptTemplates for the RAG pipeline."""
from langchain_core.prompts import PromptTemplate

ANSWER_PROMPT = PromptTemplate(
    template="""You are a helpful assistant answering questions about a YouTube video.
ONLY use the context provided from the transcript below. If the answer isn't in the context,
say "I don't know based on this video."

Format your answer in Markdown for readability: prefer short paragraphs or bullet points over a
single dense block of text, and use **bold** sparingly to highlight key facts/numbers. Keep it
proportional to the question — a simple question deserves a short answer, not padding.

Context:
{context}

Question:
{question}

Answer:""",
    input_variables=["context", "question"],
)

# Phase 3 (specs/05-memory-conversational-rag.md): rephrases a follow-up question into a
# standalone one using recent history, so retrieval works on "what about the second one?" the
# same as it would on the fully spelled-out version. Deliberately hand-rolled LCEL rather than
# LangChain's create_history_aware_retriever helper — see specs/05 for why (langchain_classic
# import-path risk post-LangChain-1.0-split).
CONDENSE_QUESTION_PROMPT = PromptTemplate(
    template="""Given the conversation so far and a follow-up question, rephrase the follow-up \
into a standalone question that can be understood without the conversation history. If the \
follow-up is already standalone, return it unchanged. Do not answer the question — only \
rephrase it.

Conversation history:
{chat_history}

Follow-up question: {question}
Standalone question:""",
    input_variables=["chat_history", "question"],
)

# Generates 2-3 short follow-up questions after an answer — filled the "empty canvas below the
# response" UX gap flagged in review. One quick non-streamed call, grounded in the same context
# so suggestions are things the video can actually answer, not generic chatbot filler.
SUGGESTIONS_PROMPT = PromptTemplate(
    template="""Based on this video transcript excerpt, the question a viewer just asked, and \
the answer they got, suggest 2-3 short, specific follow-up questions they could ask next about \
THIS video. Each must be answerable from the context below — do not invent topics not covered by \
it. Output ONLY the questions, one per line, no numbering, no extra commentary.

Context:
{context}

Question: {question}
Answer: {answer}

Follow-up questions:""",
    input_variables=["context", "question", "answer"],
)

# Phase 4 (specs/02-advanced-retrieval.md): RAG-Fusion-style query expansion — paraphrases widen
# recall for ambiguously-phrased questions, fused with the original via reciprocal rank fusion
# (rag/retrieval/retrievers.py). Gated behind MULTIQUERY_ENABLED; off by default (extra LLM call +
# N extra retrievals per question).
MULTIQUERY_PROMPT = PromptTemplate(
    template="""Generate {count} different ways to phrase the following question about a video, \
each capturing the same intent but varying wording/angle so a semantic search is more likely to \
find relevant content regardless of how it's phrased in the source. Output ONLY the rephrasings, \
one per line, no numbering, no commentary. Do not answer the question.

Question: {question}

Rephrasings:""",
    input_variables=["question", "count"],
)
