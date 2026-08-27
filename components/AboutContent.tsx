"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { AmbientBackground } from "@/components/AmbientBackground";
import { ParallaxLayer, ParallaxScene } from "@/components/ParallaxScene";
import { TiltCard } from "@/components/TiltCard";
import { ARCHITECTURE, ROADMAP } from "@/lib/architecture";

export function AboutContent() {
  return (
    <ParallaxScene className="relative min-h-screen overflow-x-hidden">
      <AmbientBackground />

      {/* Hero — one extra restrained parallax glow (matching the single-accent, single-glow
          language used everywhere else) offset from the ambient background's own glow, purely
          for the "moves with your cursor" hero effect. */}
      <section className="relative flex min-h-[65vh] flex-col items-center justify-center overflow-hidden px-6 text-center">
        <ParallaxLayer
          depth={-25}
          className="pointer-events-none absolute -top-10 left-[20%] h-72 w-72 rounded-full bg-accent/10 blur-3xl"
        />

        <ParallaxLayer depth={-8} className="relative z-10 flex flex-col items-center gap-5">
          <span className="rounded-full border border-border bg-surface-2/60 px-3 py-1 text-xs text-muted">
            How this app works
          </span>
          <h1 className="max-w-2xl text-4xl font-semibold tracking-tight sm:text-5xl">
            A <span className="accent-text">YouTube RAG chatbot</span>, built piece by piece
          </h1>
          <p className="max-w-xl text-sm text-muted sm:text-base">
            Paste a video, ask questions, get grounded answers with real citations. Here&apos;s
            everything actually running under the hood — no black boxes.
          </p>
          <Link
            href="/"
            className="mt-2 flex items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-strong"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to chat
          </Link>
        </ParallaxLayer>
      </section>

      {/* Component breakdown */}
      <section className="relative z-10 mx-auto max-w-5xl px-6 pb-16">
        <h2 className="mb-6 text-center text-xl font-semibold tracking-tight">
          The stack, component by component
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {ARCHITECTURE.map((c) => {
            const Icon = c.icon;
            return (
              <TiltCard
                key={c.name}
                maxTiltDeg={5}
                className="glass-panel flex flex-col gap-2.5 rounded-xl p-5"
              >
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/10">
                  <Icon className="h-4.5 w-4.5 text-accent" />
                </div>
                <h3 className="text-sm font-semibold">{c.name}</h3>
                <span className="text-xs font-medium text-muted">{c.tag}</span>
                <p className="text-xs leading-relaxed text-muted">{c.description}</p>
              </TiltCard>
            );
          })}
        </div>
      </section>

      {/* Roadmap — honest about what's built vs. planned */}
      <section className="relative z-10 mx-auto max-w-4xl px-6 pb-24">
        <h2 className="mb-6 text-center text-xl font-semibold tracking-tight">What&apos;s next</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {ROADMAP.map((c) => {
            const Icon = c.icon;
            return (
              <div
                key={c.name}
                className="flex flex-col gap-2.5 rounded-xl border border-dashed border-border bg-surface/40 p-5"
              >
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-2">
                  <Icon className="h-4.5 w-4.5 text-muted" />
                </div>
                <h3 className="text-sm font-semibold text-muted">{c.name}</h3>
                <span className="text-xs font-medium text-amber-400">{c.tag}</span>
                <p className="text-xs leading-relaxed text-muted">{c.description}</p>
              </div>
            );
          })}
        </div>
      </section>

      <footer className="relative z-10 pb-10 text-center">
        <Link href="/" className="text-sm accent-text hover:underline">
          ← Back to chat
        </Link>
      </footer>
    </ParallaxScene>
  );
}
