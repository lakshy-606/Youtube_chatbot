"use client";

import { useEffect, useRef, type CSSProperties, type ReactNode } from "react";

// Page-level cursor parallax: tracks mouse position and writes it to CSS custom properties
// directly via the DOM ref (not React state) so it stays smooth at 60fps without triggering a
// React re-render on every pixel of mouse movement. `ParallaxLayer` children read those vars
// with their own depth multiplier, so a "near" layer moves more than a "far" one — the actual
// depth illusion.
export function ParallaxScene({ children, className }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleMove(e: MouseEvent) {
      const el = ref.current;
      if (!el) return;
      const x = e.clientX / window.innerWidth - 0.5;
      const y = e.clientY / window.innerHeight - 0.5;
      el.style.setProperty("--mx", x.toFixed(4));
      el.style.setProperty("--my", y.toFixed(4));
    }
    window.addEventListener("mousemove", handleMove);
    return () => window.removeEventListener("mousemove", handleMove);
  }, []);

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}

export function ParallaxLayer({
  depth,
  className,
  style,
  children,
}: {
  depth: number;
  className?: string;
  style?: CSSProperties;
  children?: ReactNode;
}) {
  return (
    <div
      className={className}
      style={{
        ...style,
        transform: `translate(calc(var(--mx, 0) * ${depth}px), calc(var(--my, 0) * ${depth}px))`,
        transition: "transform 150ms ease-out",
      }}
    >
      {children}
    </div>
  );
}
