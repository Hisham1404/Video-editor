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

/** Two decimals is plenty, and it matters: raw Math.sin output like
 *  51.54675115903956% is re-serialised by the browser as 51.5468%, so the
 *  server HTML and the client style object disagree and React reports a
 *  hydration mismatch. Round here and both sides emit the same string. */
const r2 = (n: number) => Math.round(n * 100) / 100;

/** The wash for any seed. Exported so project cards can reuse it. */
export function washStyle(seed: number, rank = 3): React.CSSProperties {
  const i = seed;
  // Cool-to-warm drift, kept in a narrow, filmic band.
  const hue = r2(190 + hash(i, 1) * 60);
  const sat = r2(8 + hash(i, 2) * 10);
  // Wider shots read brighter; tighter shots sit darker and closer.
  const light = r2(58 - rank * 4.5);
  const angle = r2(120 + hash(i, 3) * 120);
  const spotX = r2(30 + hash(i, 4) * 40);
  const spotY = r2(25 + hash(i, 5) * 30);
  const lift = r2(light + 12);
  const sink = r2(Math.max(12, light - 22));
  const hue2 = r2(hue + 18);
  const sat2 = r2(sat + 4);

  // Single line, no newlines or padding — whitespace is another thing the
  // browser normalises away, and another way to desync the two renders.
  return {
    background:
      `radial-gradient(60% 70% at ${spotX}% ${spotY}%, ` +
      `hsl(${hue} ${sat}% ${lift}%) 0%, transparent 70%), ` +
      `linear-gradient(${angle}deg, hsl(${hue} ${sat}% ${light}%) 0%, ` +
      `hsl(${hue2} ${sat2}% ${sink}%) 100%)`,
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
