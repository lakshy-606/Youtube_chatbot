"""YouTube transcript fetching via Supadata's hosted API.

Originally implemented against the `youtube_transcript_api` library (direct scraping), replaced
after confirming empirically — not assumed — that YouTube's IP-based anti-bot blocking hits both
this dev sandbox AND Vercel's own shared serverless IP pool, and that free datacenter proxies
(tested against Webshare's free tier) don't get around it either; only paid residential proxies
or a hosted service that manages this server-side actually work. Supadata is the latter: free
tier is 100 requests/month, no credit card. See specs/06-phased-rollout.md's "deviations" note
for the full investigation trail.

Fetches structured (timestamped) segments, not a plain-text blob — needed for timestamp
citations (specs/02-advanced-retrieval.md's "future work" note, now built).
"""
import re

import httpx

from rag import config

VIDEO_ID_RE = re.compile(r"(?:v=|/)([0-9A-Za-z_-]{11})")
SUPADATA_TRANSCRIPT_URL = "https://api.supadata.ai/v1/youtube/transcript"


def extract_video_id(input_str: str) -> str:
    match = VIDEO_ID_RE.search(input_str)
    return match.group(1) if match else input_str


class TranscriptError(Exception):
    """Raised for any transcript-fetch failure — caught in rag/chains/rag_pipeline.py and
    re-raised as a user-facing PipelineError."""


def fetch_transcript_segments(video_id: str, language: str = "en") -> list[dict]:
    """Fetch a video's transcript as a list of {text, offset_ms, duration_ms} segments via
    Supadata's hosted API (structured mode — `text` param omitted/false — to get per-segment
    timestamps; the earlier `text=true` plain-string mode threw those away).

    Supadata returns HTTP 206 (not a typical 4xx) for "transcript unavailable" rather than an
    error status — verified directly against their docs, not assumed — so the response body's
    `error` field is checked explicitly rather than trusting the status code alone.
    """
    if not config.SUPADATA_API_KEY:
        raise TranscriptError("SUPADATA_API_KEY is not configured.")

    try:
        response = httpx.get(
            SUPADATA_TRANSCRIPT_URL,
            headers={"x-api-key": config.SUPADATA_API_KEY},
            params={"videoId": video_id, "lang": language},
            timeout=30.0,
        )
    except httpx.HTTPError as e:
        raise TranscriptError(f"Could not reach the transcript service: {e}")

    try:
        data = response.json()
    except ValueError:
        raise TranscriptError(f"Transcript service returned an invalid response (status {response.status_code}).")

    if isinstance(data, dict) and data.get("error"):
        raise TranscriptError(data.get("details") or data.get("message") or data["error"])
    if response.status_code >= 400:
        raise TranscriptError(f"Transcript service request failed (status {response.status_code}).")

    content = data.get("content") if isinstance(data, dict) else None
    if not content or not isinstance(content, list):
        raise TranscriptError("This video has no transcript available.")

    return [
        {
            "text": segment.get("text", ""),
            "offset_ms": segment.get("offset", 0),
            "duration_ms": segment.get("duration", 0),
        }
        for segment in content
        if segment.get("text")
    ]
