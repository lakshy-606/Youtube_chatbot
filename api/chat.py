"""Vercel Python serverless function backing /api/chat.

Real RAG answers with conversational memory — ingest-if-needed, condense-if-follow-up, dense
retrieval, streamed answer via rag/chains/rag_pipeline.py. Advanced retrieval (Phase 4) and
guardrails (Phase 5) layer into the pipeline module, not this file — api/chat.py stays a thin
orchestration/SSE-formatting layer, per specs/01-architecture.md: it forwards the client's full
message list straight through and lets rag_pipeline handle windowing/condensing.

Wire format verified directly against the installed `ai` npm package (see
specs/07-deployment-vercel.md): SSE lines of `data: <json>\n\n`, terminated by
`data: [DONE]\n\n`, response header `x-vercel-ai-ui-message-stream: v1`.
"""
import json
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from rag.chains.rag_pipeline import PipelineError, answer_question

app = FastAPI()

SSE_HEADERS = {
    "content-type": "text/event-stream",
    "cache-control": "no-cache",
    "connection": "keep-alive",
    "x-vercel-ai-ui-message-stream": "v1",
    "x-accel-buffering": "no",  # disable nginx-style buffering so tokens stream immediately
}


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    video_id = body.get("videoId", "")

    async def event_stream():
        text_id = str(uuid.uuid4())
        text_started = False

        yield _sse({"type": "start"})
        yield _sse({"type": "start-step"})

        try:
            async for event in answer_question(video_id, messages):
                if event["type"] == "status":
                    # transient: not saved into message history — purely an in-flight progress
                    # indicator, gone once the turn finishes (see components/ChatPanel.tsx).
                    yield _sse(
                        {
                            "type": "data-status",
                            "data": {"message": event["message"]},
                            "transient": True,
                        }
                    )
                elif event["type"] == "sources":
                    yield _sse({"type": "data-sources", "data": {"sources": event["sources"]}})
                elif event["type"] == "text":
                    if not text_started:
                        yield _sse({"type": "text-start", "id": text_id})
                        text_started = True
                    yield _sse({"type": "text-delta", "id": text_id, "delta": event["text"]})
                elif event["type"] == "warning":
                    # Not transient — the output guardrail's flag (e.g. "may not be fully
                    # grounded") should stay visible on the message, unlike ephemeral status.
                    yield _sse({"type": "data-warning", "data": {"message": event["message"]}})
                elif event["type"] == "suggestions":
                    yield _sse(
                        {"type": "data-suggestions", "data": {"suggestions": event["suggestions"]}}
                    )
        except PipelineError as e:
            if not text_started:
                yield _sse({"type": "text-start", "id": text_id})
                text_started = True
            yield _sse({"type": "error", "errorText": str(e)})
        except Exception as e:  # last-resort guard so a bug surfaces in the UI, not a hung stream
            if not text_started:
                yield _sse({"type": "text-start", "id": text_id})
                text_started = True
            yield _sse({"type": "error", "errorText": f"Unexpected error: {e}"})

        if text_started:
            yield _sse({"type": "text-end", "id": text_id})
        yield _sse({"type": "finish-step"})
        yield _sse({"type": "finish"})
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), headers=SSE_HEADERS)
