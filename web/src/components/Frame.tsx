"use client";

import { type Slot, isGap, shotSizeRank } from "@/lib/template";

/**
 * A stand-in for a frame of footage.
 *
 * There is no real video yet, so rather than pull stock photos — which would
 * misrepresent someone's own footage — each shot gets a deterministic, filmic
 * wash derived from its index and shot size. Desaturated on purpose: it should
 * read as "a frame goes here", carry enough difference that you can tell shots
 * apart and see the order, and never compete with the interface.
 *
 * Swap the body of this component for a real poster frame once stage 1 can
 * extract them; nothing else needs to change.
 */

function hash(n: number, salt: number) {
  const x = Math.sin(n * 12.9898 + salt * 78.233) * 43758.5453;
  return x - Math.floor(x);
}

/** The wash for any seed. Exported so project cards can reuse it. */
export function washStyle(seed: number, rank = 3): React.CSSProperties {
  const i = seed;
  // Cool-to-warm drift, kept in a narrow, filmic band.
  const hue = 190 + hash(i, 1) * 60;
  const sat = 8 + hash(i, 2) * 10;
  // Wider shots read brighter; tighter shots sit darker and closer.
  const light = 58 - rank * 4.5;
  const angle = 120 + hash(i, 3) * 120;
  const spot = 30 + hash(i, 4) * 40;

  return {
    background: `
      radial-gradient(60% 70% at ${spot}% ${25 + hash(i, 5) * 30}%,
        hsl(${hue} ${sat}% ${light + 12}%) 0%,
        transparent 70%),
      linear-gradient(${angle}deg,
        hsl(${hue} ${sat}% ${light}%) 0%,
        hsl(${hue + 18} ${sat + 4}% ${Math.max(12, light - 22)}%) 100%)
    `,
  };
}

export function frameStyle(slot: Slot): React.CSSProperties {
  return washStyle(slot.index, shotSizeRank(slot.shot_size));
}

export default function Frame({
  slot,
  className = "",
  rounded = 8,
  showMark = false,
}: {
  slot: Slot;
  className?: string;
  rounded?: number;
  showMark?: boolean;
}) {
  const gap = isGap(slot);

  if (gap) {
    return (
      <div
        className={`grid place-items-center ${className}`}
        style={{
          borderRadius: rounded,
          border: "1.5px dashed var(--accent)",
          background: "var(--accent-soft)",
        }}
        aria-hidden
      >
        {showMark && (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path
              d="M12 6v12M6 12h12"
              stroke="var(--accent)"
              strokeWidth="1.6"
              strokeLinecap="round"
            />
          </svg>
        )}
      </div>
    );
  }

  return (
    <div
      className={className}
      style={{ ...frameStyle(slot), borderRadius: rounded }}
      aria-hidden
    />
  );
}
