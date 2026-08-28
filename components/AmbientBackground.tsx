// Fixed, full-viewport, behind everything. A single, slow, low-opacity glow behind the chat
// panel — restrained ambient depth rather than several bouncing colorful orbs (an earlier,
// more playful version of this component; dropped in favor of a more professional look — see
// specs/06-phased-rollout.md). `pointer-events-none` so it never intercepts clicks.
export function AmbientBackground() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div
        className="absolute left-1/2 top-1/2 h-[60vw] w-[60vw] max-h-[700px] max-w-[700px] rounded-full blur-3xl"
        style={{
          background:
            "radial-gradient(circle, color-mix(in srgb, var(--accent) 20%, transparent) 0%, transparent 70%)",
          animation: "glow-drift 16s ease-in-out infinite",
        }}
      />
    </div>
  );
}
