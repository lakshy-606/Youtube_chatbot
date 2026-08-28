"""rag/ingestion/transcript.py — extract_video_id() and fetch_transcript_segments()'s parsing/
error-handling logic. The actual Supadata HTTP call is mocked; nothing here hits the network.
"""
from unittest.mock import patch

import httpx
import pytest

from rag.ingestion.transcript import TranscriptError, extract_video_id, fetch_transcript_segments


@pytest.mark.parametrize(
    "input_str, expected",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s", "dQw4w9WgXcQ"),
        ("https://youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),  # bare ID, no v=/ separator to match — falls through as-is
    ],
)
def test_extract_video_id(input_str, expected):
    assert extract_video_id(input_str) == expected


def _mock_response(json_body, status_code=200):
    request = httpx.Request("GET", "https://api.supadata.ai/v1/youtube/transcript")
    return httpx.Response(status_code, json=json_body, request=request)


def test_fetch_transcript_segments_parses_structured_content():
    body = {
        "content": [
            {"text": "Hello there", "offset": 0, "duration": 1000},
            {"text": "", "offset": 1000, "duration": 500},  # falsy text segments are dropped
            {"text": "General Kenobi", "offset": 1500, "duration": 1200},
        ]
    }
    with patch("httpx.get", return_value=_mock_response(body)):
        segments = fetch_transcript_segments("abc123")

    assert segments == [
        {"text": "Hello there", "offset_ms": 0, "duration_ms": 1000},
        {"text": "General Kenobi", "offset_ms": 1500, "duration_ms": 1200},
    ]


def test_fetch_transcript_segments_raises_on_explicit_error_field():
    # Supadata returns HTTP 206 (not a 4xx) for "transcript unavailable" — the `error` field in
    # the body is the real signal, not the status code.
    body = {"error": "transcript-unavailable", "message": "No transcript for this video."}
    with patch("httpx.get", return_value=_mock_response(body, status_code=206)):
        with pytest.raises(TranscriptError, match="No transcript for this video."):
            fetch_transcript_segments("abc123")


def test_fetch_transcript_segments_raises_on_empty_content():
    with patch("httpx.get", return_value=_mock_response({"content": []})):
        with pytest.raises(TranscriptError, match="no transcript available"):
            fetch_transcript_segments("abc123")


def test_fetch_transcript_segments_raises_on_network_error():
    with patch("httpx.get", side_effect=httpx.ConnectTimeout("timed out")):
        with pytest.raises(TranscriptError, match="Could not reach the transcript service"):
            fetch_transcript_segments("abc123")


def test_fetch_transcript_segments_requires_api_key(monkeypatch):
    monkeypatch.setattr("rag.config.SUPADATA_API_KEY", "")
    with pytest.raises(TranscriptError, match="SUPADATA_API_KEY"):
        fetch_transcript_segments("abc123")
