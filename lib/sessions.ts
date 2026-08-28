import type { UIMessage } from "ai";

// Client-side only, per-browser "temporary db" — matches the product ask directly: no accounts,
// no server-side storage, just persistence across reloads within the same browser. Capped at
// MAX_SESSIONS chat sessions; each session's own messages are stored separately so switching
// sessions doesn't require loading everyone's history at once.

export type ChatSession = {
  id: string;
  videoId: string;
  videoTitle: string;
  videoThumbnail: string;
  videoAuthor?: string;
  createdAt: number;
};

export const MAX_SESSIONS = 3;

const SESSIONS_KEY = "yt-chatbot:sessions";
const ACTIVE_KEY = "yt-chatbot:active";
const messagesKey = (sessionId: string) => `yt-chatbot:messages:${sessionId}`;

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

function safeGet(key: string): string | null {
  if (!isBrowser()) return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null; // private browsing / storage disabled — degrade to no persistence
  }
}

function safeSet(key: string, value: string): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // quota exceeded or storage disabled — silently skip persistence rather than crash the UI
  }
}

function safeRemove(key: string): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.removeItem(key);
  } catch {
    // ignore
  }
}

export function loadSessions(): ChatSession[] {
  const raw = safeGet(SESSIONS_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveSessions(sessions: ChatSession[]): void {
  safeSet(SESSIONS_KEY, JSON.stringify(sessions));
}

export function loadMessages(sessionId: string): UIMessage[] {
  const raw = safeGet(messagesKey(sessionId));
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveMessages(sessionId: string, messages: UIMessage[]): void {
  safeSet(messagesKey(sessionId), JSON.stringify(messages));
}

export function deleteSessionData(sessionId: string): void {
  safeRemove(messagesKey(sessionId));
}

export function loadActiveSessionId(): string | null {
  return safeGet(ACTIVE_KEY);
}

export function saveActiveSessionId(sessionId: string): void {
  safeSet(ACTIVE_KEY, sessionId);
}
