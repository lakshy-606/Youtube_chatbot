"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import Image from "next/image";
import type { ChatSession } from "@/lib/sessions";

// Mirrors FlashCards' positioning on the opposite side — fills the empty left-hand space with
// the active video's own thumbnail/title instead of leaving it as bare ambient background.
// Rectangular (native video aspect ratio) rather than circular: a circular crop loses most of a
// 16:9 thumbnail's actual content, which reads as worse, not more polished, at this larger size.
export function VideoShowcase({
  sessions,
  activeId,
  onSelect,
}: {
  sessions: ChatSession[];
  activeId: string | null;
  onSelect: (id: string) => void;
}) {
  const session = sessions.find((s) => s.id === activeId) ?? null;
  const showNav = sessions.length > 1 && session != null;

  function step(direction: 1 | -1) {
    if (!session) return;
    const idx = sessions.findIndex((s) => s.id === session.id);
    const target = sessions[(idx + direction + sessions.length) % sessions.length];
    onSelect(target.id);
  }

  return (
    <div className="pointer-events-none absolute left-6 top-1/2 z-10 hidden w-72 -translate-y-1/2 xl:block">
      {session ? (
        <div className="glass-panel pointer-events-auto overflow-hidden rounded-xl shadow-xl shadow-black/30">
          <div className="relative aspect-video w-full">
            <Image
              src={session.videoThumbnail}
              alt=""
              fill
              sizes="288px"
              className="object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent" />
            {showNav && (
              <>
                <button
                  onClick={() => step(-1)}
                  aria-label="Switch to previous chat"
                  title="Previous chat"
                  className="absolute left-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full bg-black/50 text-white backdrop-blur-sm transition-colors hover:bg-black/70"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  onClick={() => step(1)}
                  aria-label="Switch to next chat"
                  title="Next chat"
                  className="absolute right-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full bg-black/50 text-white backdrop-blur-sm transition-colors hover:bg-black/70"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </>
            )}
          </div>
          <div className="p-4">
            <span className="text-xs font-medium uppercase tracking-wide text-muted">
              Now chatting about
            </span>
            <h3 className="mt-1.5 text-sm font-semibold leading-snug text-foreground">
              {session.videoTitle}
            </h3>
            {session.videoAuthor && (
              <p className="mt-1 text-xs text-muted">{session.videoAuthor}</p>
            )}
          </div>
        </div>
      ) : (
        <div className="glass-panel pointer-events-auto rounded-xl p-5">
          <p className="text-xs leading-relaxed text-muted">
            Start a chat to see the video&apos;s details here.
          </p>
        </div>
      )}
    </div>
  );
}
