"use client";

import { MessageSquareText, Plus, X } from "lucide-react";
import Image from "next/image";
import { CreditsBadge } from "@/components/CreditsBadge";
import { GithubBadge } from "@/components/GithubBadge";
import { MAX_SESSIONS, type ChatSession } from "@/lib/sessions";

// A slim horizontal strip of circular thumbnail "tabs" — replaces the old fixed sidebar. Its own
// full-width top bar, detached from the chat window below it rather than stacked in one card.
export function SessionDock({
  sessions,
  activeId,
  onSelect,
  onDelete,
  onNewChat,
}: {
  sessions: ChatSession[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onNewChat: () => void;
}) {
  const atLimit = sessions.length >= MAX_SESSIONS;

  return (
    <div className="glass-panel relative z-20 flex w-full flex-shrink-0 items-center gap-4 border-b-0 px-6 py-3.5 shadow-lg shadow-black/20 after:absolute after:inset-x-0 after:bottom-0 after:h-px after:bg-gradient-to-r after:from-transparent after:via-accent/40 after:to-transparent">
      <div className="hidden items-center gap-2 sm:flex">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/10">
          <MessageSquareText className="h-4 w-4 text-accent" />
        </div>
        <span className="text-sm font-semibold tracking-tight text-foreground">YouTube RAG</span>
      </div>

      <div className="hidden h-6 w-px bg-border sm:block" />

      <div className="flex flex-1 items-center gap-2 overflow-x-auto scrollbar-thin">
        {sessions.map((s) => {
          const isActive = s.id === activeId;
          return (
            <div key={s.id} className="group relative flex-shrink-0">
              <button
                onClick={() => onSelect(s.id)}
                title={s.videoTitle}
                className={`relative h-9 w-9 overflow-hidden rounded-full transition-all ${
                  isActive
                    ? "ring-2 ring-accent ring-offset-2 ring-offset-surface"
                    : "opacity-60 hover:opacity-100"
                }`}
              >
                <Image src={s.videoThumbnail} alt="" fill sizes="36px" className="object-cover" />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(s.id);
                }}
                aria-label="Close chat"
                className="absolute -right-1 -top-1 hidden h-4 w-4 items-center justify-center rounded-full bg-surface-2 text-muted opacity-0 transition group-hover:flex group-hover:opacity-100 hover:bg-red-500/80 hover:text-white"
              >
                <X className="h-2.5 w-2.5" />
              </button>
            </div>
          );
        })}

        <button
          onClick={onNewChat}
          disabled={atLimit}
          title={atLimit ? `Max ${MAX_SESSIONS} chats — close one to start a new one` : "New chat"}
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full border border-dashed border-border text-muted transition-colors hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-30"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      <div className="flex flex-shrink-0 items-center gap-2.5">
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            atLimit ? "bg-amber-400/10 text-amber-400" : "bg-surface-2 text-muted"
          }`}
        >
          {sessions.length}/{MAX_SESSIONS}
        </span>
        <GithubBadge />
        <CreditsBadge />
      </div>
    </div>
  );
}
