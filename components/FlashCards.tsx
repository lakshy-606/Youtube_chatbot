"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { APP_FACTS } from "@/lib/facts";

const ROTATE_MS = 30_000;

// The right-side rotating info widget — auto-advances every 30s, clicking any card jumps to
// /about for the full breakdown. Hidden below `xl` since the layout doesn't have room to spare
// on narrower screens without crowding the main chat card.
export function FlashCards() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setIndex((i) => (i + 1) % APP_FACTS.length);
    }, ROTATE_MS);
    return () => clearInterval(id);
  }, []);

  const fact = APP_FACTS[index];
  const Icon = fact.icon;

  return (
    <div className="pointer-events-none absolute right-6 top-1/2 z-10 hidden -translate-y-1/2 xl:block">
      <Link
        href="/about"
        className="glass-panel pointer-events-auto block w-64 rounded-xl shadow-xl transition-colors hover:border-accent/40"
      >
        <div key={index} style={{ animation: "card-in 0.4s ease" }} className="flex flex-col gap-2 p-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/10">
            <Icon className="h-4.5 w-4.5 text-accent" />
          </div>
          <span className="text-xs font-medium uppercase tracking-wide text-muted">
            {fact.tag}
          </span>
          <h3 className="text-sm font-semibold text-foreground">{fact.title}</h3>
          <p className="text-xs leading-relaxed text-muted">{fact.description}</p>
          <span className="mt-1 flex items-center gap-1 text-xs font-medium accent-text">
            Learn more <ArrowRight className="h-3 w-3" />
          </span>
        </div>
      </Link>

      <div className="mt-3 flex justify-center gap-1.5">
        {APP_FACTS.map((_, i) => (
          <span
            key={i}
            className={`h-1 rounded-full transition-all ${
              i === index ? "w-4 bg-accent" : "w-1 bg-border"
            }`}
          />
        ))}
      </div>
    </div>
  );
}
