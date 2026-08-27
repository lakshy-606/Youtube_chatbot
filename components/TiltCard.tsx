"use client";

import { useRef, useState, type CSSProperties, type ReactNode } from "react";

// A CSS-only 3D tilt effect (perspective + rotateX/rotateY toward the cursor) — no WebGL/Three.js
// dependency. Chosen over a full 3D-rendered scene as the right amount of "fancy" for a sidebar
// video card: noticeable, tasteful, doesn't fight the chat UI for attention.
export function TiltCard({
  children,
  className,
  maxTiltDeg = 10,
}: {
  children: ReactNode;
  className?: string;
  maxTiltDeg?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [style, setStyle] = useState<CSSProperties>({
    transform: "perspective(900px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)",
    transition: "transform 400ms cubic-bezier(0.22, 1, 0.36, 1)",
  });

  function handleMouseMove(e: React.MouseEvent<HTMLDivElement>) {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width - 0.5;
    const py = (e.clientY - rect.top) / rect.height - 0.5;
    setStyle({
      transform: `perspective(900px) rotateX(${(-py * maxTiltDeg).toFixed(2)}deg) rotateY(${(
        px * maxTiltDeg
      ).toFixed(2)}deg) scale3d(1.015, 1.015, 1.015)`,
      transition: "transform 80ms ease-out",
    });
  }

  function handleMouseLeave() {
    setStyle({
      transform: "perspective(900px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)",
      transition: "transform 400ms cubic-bezier(0.22, 1, 0.36, 1)",
    });
  }

  return (
    <div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{ ...style, transformStyle: "preserve-3d", willChange: "transform" }}
      className={className}
    >
      {children}
    </div>
  );
}
