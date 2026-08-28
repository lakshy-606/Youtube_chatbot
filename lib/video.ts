// Mirrors rag/ingestion/transcript.py's extract_video_id — kept in sync intentionally, not
// imported (Python/TS boundary), so a change to one should be checked against the other.
const VIDEO_ID_RE = /(?:v=|\/)([0-9A-Za-z_-]{11})/;

export function extractVideoId(input: string): string {
  const match = VIDEO_ID_RE.exec(input);
  return match ? match[1] : input;
}
