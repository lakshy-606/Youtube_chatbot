"use client";

import { useState, useSyncExternalStore } from "react";
import { AmbientBackground } from "@/components/AmbientBackground";
import { ChatPanel } from "@/components/ChatPanel";
import { FlashCards } from "@/components/FlashCards";
import { NewChatDialog } from "@/components/NewChatDialog";
import { SessionDock } from "@/components/SessionDock";
import { VideoShowcase } from "@/components/VideoShowcase";
import { extractVideoId } from "@/lib/video";
import {
  MAX_SESSIONS,
  deleteSessionData,
  loadActiveSessionId,
  loadSessions,
  saveActiveSessionId,
  saveSessions,
  type ChatSession,
} from "@/lib/sessions";

// The canonical hydration-safe "are we past the client mount" flag: nothing ever changes this
// external store, so `subscribe` is a no-op — the point is only that server/client snapshots
// differ, letting the first client render match the server's before real data takes over.
function subscribeNever() {
  return () => {};
}
function useIsClient(): boolean {
  return useSyncExternalStore(
    subscribeNever,
    () => true,
    () => false
  );
}

export default function Home() {
  // Lazy initializers: on the server these read `window`-less helpers that safely return
  // empty/null; on the client they read the real localStorage state during mount. Real content
  // only renders once `hydrated` is true (below), so server and client agree on the first paint
  // regardless of what these initializers actually computed — no hydration mismatch.
  const [sessions, setSessions] = useState<ChatSession[]>(() => loadSessions());
  const [activeId, setActiveId] = useState<string | null>(() => {
    const loaded = loadSessions();
    const saved = loadActiveSessionId();
    if (saved && loaded.some((s) => s.id === saved)) return saved;
    return loaded[0]?.id ?? null;
  });
  const [showNewChat, setShowNewChat] = useState(false);
  const hydrated = useIsClient();

  const activeSession = sessions.find((s) => s.id === activeId) ?? null;

  async function handleCreateChat(videoIdOrUrl: string) {
    if (sessions.length >= MAX_SESSIONS) {
      throw new Error(`You can have at most ${MAX_SESSIONS} chats open — close one first.`);
    }
    const videoId = extractVideoId(videoIdOrUrl);
    const res = await fetch(`/api/video-meta?videoId=${encodeURIComponent(videoId)}`);
    if (!res.ok) {
      throw new Error("Could not find that video — check the ID/URL and try again.");
    }
    const meta = await res.json();

    const session: ChatSession = {
      id: crypto.randomUUID(),
      videoId,
      videoTitle: meta.title ?? videoId,
      videoThumbnail: meta.thumbnailUrl,
      videoAuthor: meta.author,
      createdAt: Date.now(),
    };

    const next = [...sessions, session];
    setSessions(next);
    saveSessions(next);
    setActiveId(session.id);
    saveActiveSessionId(session.id);
    setShowNewChat(false);
  }

  function handleSelect(id: string) {
    setActiveId(id);
    saveActiveSessionId(id);
  }

  function handleDelete(id: string) {
    const next = sessions.filter((s) => s.id !== id);
    setSessions(next);
    saveSessions(next);
    deleteSessionData(id);
    if (activeId === id) {
      const fallback = next[0]?.id ?? null;
      setActiveId(fallback);
      if (fallback) saveActiveSessionId(fallback);
    }
  }

  if (!hydrated) {
    return (
      <div className="relative flex h-screen items-center justify-center overflow-hidden">
        <AmbientBackground />
        <p className="text-sm text-muted">Loading…</p>
      </div>
    );
  }

  return (
    <div className="relative flex h-screen flex-col overflow-hidden">
      <AmbientBackground />

      {/* Full-width header — a real top bar, not just detached-but-narrow. */}
      <SessionDock
        sessions={sessions}
        activeId={activeId}
        onSelect={handleSelect}
        onDelete={handleDelete}
        onNewChat={() => setShowNewChat(true)}
      />

      {/* The stage below the header: showcase / chat card / flash cards. */}
      <div className="relative flex flex-1 items-center justify-center overflow-hidden p-3 sm:p-8">
        <VideoShowcase sessions={sessions} activeId={activeId} onSelect={handleSelect} />
        <FlashCards />

        <div className="glass-panel relative z-10 flex h-full max-h-[820px] w-full max-w-3xl flex-col overflow-hidden rounded-2xl shadow-2xl shadow-black/40">
          {activeSession ? (
            <ChatPanel key={activeSession.id} session={activeSession} />
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
              <h2 className="text-2xl font-semibold tracking-tight">Start your first chat</h2>
              <p className="max-w-sm text-sm text-muted">
                Paste a YouTube video and ask questions about it — up to {MAX_SESSIONS} chats at once.
              </p>
              <button
                onClick={() => setShowNewChat(true)}
                className="rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-strong"
              >
                New chat
              </button>
            </div>
          )}
        </div>

        {showNewChat && (
          <NewChatDialog onClose={() => setShowNewChat(false)} onCreate={handleCreateChat} />
        )}
      </div>
    </div>
  );
}
