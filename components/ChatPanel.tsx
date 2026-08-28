"use client";

import { Chat, useChat } from "@ai-sdk/react";
import { DefaultChatTransport, type UIMessage } from "ai";
import { Loader2, MapPin, Send, TriangleAlert } from "lucide-react";
import Image from "next/image";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { loadMessages, saveMessages } from "@/lib/sessions";
import type { ChatSession } from "@/lib/sessions";

type SourceItem = { start_ms: number; label: string; url: string };

function SourceChips({ sources }: { sources: SourceItem[] }) {
  if (!sources.length) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {sources.map((s, i) => (
        <a
          key={i}
          href={s.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 rounded-full border border-border bg-surface-2 px-2.5 py-1 text-xs text-muted transition-colors hover:border-accent/50 hover:text-accent"
        >
          <MapPin className="h-3 w-3" />
          {s.label}
        </a>
      ))}
    </div>
  );
}

function GuardWarning({ message }: { message: string }) {
  return (
    <div className="mt-2 flex items-start gap-1.5 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-300">
      <TriangleAlert className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
      <span>{message}</span>
    </div>
  );
}

function SuggestionPills({
  suggestions,
  onPick,
  disabled,
}: {
  suggestions: string[];
  onPick: (text: string) => void;
  disabled: boolean;
}) {
  if (!suggestions.length) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {suggestions.map((s, i) => (
        <button
          key={i}
          onClick={() => onPick(s)}
          disabled={disabled}
          className="rounded-lg border border-border bg-surface-2/60 px-3 py-1.5 text-left text-xs text-foreground transition-colors hover:border-accent/50 hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {s}
        </button>
      ))}
    </div>
  );
}

export function ChatPanel({ session }: { session: ChatSession }) {
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  // Created here (not in app/page.tsx) specifically so `onData` can update local state directly
  // — the AI SDK only accepts onData at Chat-construction time, not on useChat({chat}) when
  // passing an existing instance. Rebuilt from localStorage whenever the session changes (this
  // component remounts per-session anyway, via `key={session.id}` in app/page.tsx).
  const chat = useMemo(
    () =>
      new Chat<UIMessage>({
        id: session.id,
        messages: loadMessages(session.id),
        transport: new DefaultChatTransport({ body: { videoId: session.videoId } }),
        onData: (part) => {
          if (part.type === "data-status") {
            setStatusMessage((part.data as { message: string }).message);
          }
        },
      }),
    [session.id, session.videoId]
  );

  const { messages, sendMessage, status, error } = useChat({ chat });
  const [input, setInput] = useState("");

  const isBusy = status === "submitted" || status === "streaming";
  const bottomRef = useRef<HTMLDivElement>(null);

  // Persist this session's messages to localStorage every time they change — this is the
  // "temporary db" the sidebar/session list reads from on the next page load.
  useEffect(() => {
    saveMessages(session.id, messages);
  }, [session.id, messages]);

  // Auto-scroll to the newest content — fires on every message-list change AND on each streamed
  // token (status flips through "streaming" repeatedly as deltas arrive), so it tracks a
  // response as it's still being written, not just once it finishes.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, status]);

  function ask(text: string) {
    if (!text.trim() || isBusy) return;
    setStatusMessage(null); // clear any stale status from a previous turn before this one starts
    sendMessage({ text: text.trim() });
    setInput("");
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    ask(input);
  }

  return (
    <div className="flex h-full flex-1 flex-col overflow-hidden">
      {/* Minimal — the full video card lives in the left-side VideoShowcase on wide screens;
          this is just enough context to stay usable when that's hidden (below `xl`). */}
      <div className="flex items-center gap-2.5 border-b border-border px-4 py-2.5">
        <div className="relative h-7 w-7 flex-shrink-0 overflow-hidden rounded-md">
          <Image src={session.videoThumbnail} alt="" fill sizes="28px" className="object-cover" />
        </div>
        <p className="truncate text-xs font-medium text-muted">{session.videoTitle}</p>
      </div>

      <div className="flex flex-1 flex-col overflow-y-auto scrollbar-thin">
        <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 p-6">
          {messages.length === 0 && (
            <p className="text-center text-sm text-muted">Ask something about the video below.</p>
          )}
          {messages.map((m) => {
            const isUser = m.role === "user";
            const textContent = m.parts
              .filter((p) => p.type === "text")
              .map((p) => (p as { text: string }).text)
              .join("");
            const sources = m.parts.find((p) => p.type === "data-sources") as
              | { data: { sources: SourceItem[] } }
              | undefined;
            const suggestions = m.parts.find((p) => p.type === "data-suggestions") as
              | { data: { suggestions: string[] } }
              | undefined;
            const warning = m.parts.find((p) => p.type === "data-warning") as
              | { data: { message: string } }
              | undefined;

            return (
              <div key={m.id} className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}>
                <div
                  className={
                    isUser
                      ? "max-w-lg rounded-2xl rounded-br-sm bg-accent px-4 py-2.5 text-sm text-white"
                      : "glass-panel max-w-2xl rounded-2xl rounded-bl-sm px-4 py-3 text-sm"
                  }
                >
                  {isUser ? (
                    textContent
                  ) : (
                    <div className="prose prose-invert prose-sm max-w-none prose-p:my-1.5 prose-ul:my-1.5 prose-li:my-0.5 prose-strong:text-foreground">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{textContent}</ReactMarkdown>
                    </div>
                  )}
                  {sources && <SourceChips sources={sources.data.sources} />}
                  {warning && <GuardWarning message={warning.data.message} />}
                </div>
                {suggestions && (
                  <div className="w-full max-w-2xl">
                    <SuggestionPills
                      suggestions={suggestions.data.suggestions}
                      onPick={ask}
                      disabled={isBusy}
                    />
                  </div>
                )}
              </div>
            );
          })}
          {isBusy && (
            <div className="flex items-center gap-2 text-xs text-muted">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              {statusMessage ?? "Thinking…"}
            </div>
          )}
          {error && <p className="text-xs text-red-400">{error.message}</p>}
          <div ref={bottomRef} />
        </div>
      </div>

      <form onSubmit={handleSubmit} className="border-t border-border p-4">
        <div className="mx-auto flex w-full max-w-3xl gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask something about the video…"
            className="flex-1 rounded-lg border border-border bg-surface-2 px-4 py-2.5 text-sm outline-none focus:border-accent"
          />
          <button
            type="submit"
            disabled={isBusy || !input.trim()}
            className="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-strong disabled:opacity-40"
          >
            <Send className="h-4 w-4" />
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
