"use client";

const LINKEDIN_URL = "https://www.linkedin.com/in/lakshya-singh596/";

// A small "!" badge, far right of the header — hover reveals attribution, click opens LinkedIn.
export function CreditsBadge() {
  return (
    <a
      href={LINKEDIN_URL}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Created by Lakshya Singh — view LinkedIn"
      className="group relative flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full border border-border text-xs font-semibold text-muted transition-colors hover:border-accent hover:text-accent"
    >
      !
      <span className="pointer-events-none absolute right-0 top-full z-20 mt-2 whitespace-nowrap rounded-md border border-border bg-surface-2 px-2.5 py-1.5 text-xs text-foreground opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100">
        Created by Lakshya Singh
      </span>
    </a>
  );
}
