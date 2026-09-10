"use client";

import clsx from "clsx";
import Frame from "@/components/Frame";
import {
  type Slot,
  type Template,
  durationBeats,
  durationSeconds,
  isGap,
  totalBeats,
} from "@/lib/template";

/**
 * What the cut actually looks like.
 *
 * The previous version showed the edit as abstract bars, which told you the
 * rhythm but not what was in any shot. This puts a frame on screen: one large
 * poster for whatever is selected, and a strip of every shot beneath it in
 * order, each as wide as it is long.
 *
 * Reels are vertical, so the poster is 9:16 and capped in height rather than
 * given the full viewport — on a laptop a full-height vertical video pushes
 * everything else off the page.
 */

export function Poster({
  slot,
  bpm,
  total,
}: {
  slot: Slot;
  bpm: number;
  total: number;
}) {
  const gap = isGap(slot);
  return (
    <figure className="relative mx-auto w-full max-w-[248px] sm:max-w-[288px]">
      <Frame
        slot={slot}
        rounded={14}
        showMark
        className="aspect-[9/16] w-full"
      />

      {/* Meta sits on the frame the way a viewer's HUD does — present, but
          not competing with the image. */}
      <figcaption className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-2 p-3">
        <span
          className="micro rounded-full px-2 py-0.5"
          style={{
            background: "rgba(0,0,0,0.45)",
            color: "#fff",
            backdropFilter: "blur(6px)",
          }}
        >
          {slot.index + 1} / {total}
        </span>
        <span
          className="micro rounded-full px-2 py-0.5"
          style={{
            background: gap ? "var(--accent)" : "rgba(0,0,0,0.45)",
            color: gap ? "#fff" : "#fff",
            backdropFilter: "blur(6px)",
          }}
        >
          {gap ? "needs a clip" : slot.shot_size}
        </span>
      </figcaption>

      <div className="pointer-events-none absolute inset-x-0 bottom-0 p-3">
        <span
          className="micro num rounded-full px-2 py-0.5"
          style={{
            background: "rgba(0,0,0,0.45)",
            color: "#fff",
            backdropFilter: "blur(6px)",
          }}
        >
          {durationBeats(slot)} beats · {durationSeconds(slot, bpm).toFixed(2)}s
        </span>
      </div>
    </figure>
  );
}

/**
 * Every shot in order. Width is duration, so the cut's rhythm is still legible
 * — you can see the chorus tighten — but now each block carries an image.
 */
export function Filmstrip({
  template,
  selected,
  onSelect,
}: {
  template: Template;
  selected: number | null;
  onSelect: (i: number) => void;
}) {
  const beats = totalBeats(template);
  const n = template.slots.length;
  const GAP = 4; // px between blocks
  // Each block's share is of the space left after the gaps, otherwise the
  // gaps push the last blocks past the right edge.
  const gapShare = (GAP * (n - 1)) / n;

  return (
    <div className="w-full">
      <div
        className="flex w-full overflow-x-auto"
        style={{ gap: GAP }}
        role="listbox"
        aria-label="Shots in the cut"
      >
        {template.slots.map((slot) => {
          const active = selected === slot.index;
          const share = (durationBeats(slot) / beats) * 100;
          return (
            <button
              key={slot.index}
              role="option"
              aria-selected={active}
              onClick={() => onSelect(slot.index)}
              title={`${slot.shot_size} · ${slot.description}`}
              aria-label={`Shot ${slot.index + 1}, ${slot.shot_size}, ${
                isGap(slot) ? "no clip matched" : "matched"
              }. ${slot.description}`}
              className={clsx(
                "press relative shrink-0 grow-0 overflow-hidden rounded-md",
                "focus-visible:outline-offset-4",
              )}
              style={{
                flexBasis: `calc(${share}% - ${gapShare}px)`,
                // Below this a block is neither visible nor tappable. The
                // strip scrolls rather than shrinking shots into slivers.
                minWidth: 26,
                outline: active ? "2px solid var(--ink)" : "none",
                outlineOffset: 2,
              }}
            >
              <Frame slot={slot} rounded={6} className="aspect-[9/14] w-full" />
              {!active && (
                <span
                  className="absolute inset-0"
                  style={{
                    background: "var(--bg)",
                    opacity: selected === null ? 0 : 0.42,
                    transition: "opacity var(--t-fast) var(--ease-out)",
                  }}
                />
              )}
            </button>
          );
        })}
      </div>

      <p className="micro mt-2">
        Each block is one shot — as wide as it holds. Dashed blocks have no clip
        yet.
      </p>
    </div>
  );
}
