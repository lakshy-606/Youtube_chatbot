"use client";

import { useState, type FormEvent } from "react";

export function NewChatDialog({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (videoIdOrUrl: string) => Promise<void>;
}) {
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!value.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      await onCreate(value.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start this chat.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="glass-panel w-full max-w-md rounded-2xl p-6 shadow-2xl"
      >
        <h2 className="mb-1 text-lg font-semibold">Start a new chat</h2>
        <p className="mb-4 text-sm text-muted">Paste a YouTube video ID or URL.</p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <input
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="e.g. https://youtube.com/watch?v=... or dQw4w9WgXcQ"
            className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent"
          />
          {error && <p className="text-xs text-red-400">{error}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-sm text-muted hover:bg-white/5"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !value.trim()}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-strong disabled:opacity-40"
            >
              {loading ? "Loading…" : "Start chat"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
