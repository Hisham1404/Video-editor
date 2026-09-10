"use client";

import clsx from "clsx";
import {
  type Slot,
  type Template,
  SHOT_SIZE_ORDER,
  absoluteBeats,
  durationBeats,
  isGap,
  shotSizeRank,
  totalBeats,
} from "@/lib/template";

/**
 * The cut, as a silhouette.
 *
 * Width is duration in beats. Height is shot size — widest shot tallest — so
 * the reference's shot-size rhythm reads as a shape you take in at a glance
 * instead of a grid you have to parse row by row. Because it carries no text,
 * it fits any viewport without horizontal scrolling.
 *
 * Nothing here is measured in seconds. Change the tempo and not one bar moves.
 */

const GUTTER = 0.35; // % of width left between bars

function heightFor(slot: Slot) {
  const rank = shotSizeRank(slot.shot_size); // 0 = extreme wide
  return 1 - (rank / (SHOT_SIZE_ORDER.length - 1)) * 0.62; // 1.0 → 0.38
}

interface Props {
  template: Template;
  selected: number | null;
  onSelect: (i: number) => void;
}

export default function Strip({ template, selected, onSelect }: Props) {
  const beats = totalBeats(template);
  const phrase = template.beats_per_phrase;
  const phrases = Math.floor(beats / phrase);

  return (
    <div className="w-full">
      <div className="relative h-[104px] w-full sm:h-[132px]">
        {/* Phrase markers only. Every bar line would be noise at this size,
            and the phrase is the structure that actually shapes a reel. */}
        {Array.from({ length: phrases }, (_, i) => {
          const b = (i + 1) * phrase;
          if (b >= beats) return null;
          return (
            <span
              key={b}
              aria-hidden
              className="absolute inset-y-0 w-px"
              style={{ left: `${(b / beats) * 100}%`, background: "var(--line)" }}
            />
          );
        })}

        {template.slots.map((slot) => {
          const gap = isGap(slot);
          const active = selected === slot.index;
          const left = (absoluteBeats(slot.start) / beats) * 100;
          const width = (durationBeats(slot) / beats) * 100;

          return (
            <button
              key={slot.index}
              onClick={() => onSelect(slot.index)}
              aria-pressed={active}
              aria-label={`Slot ${slot.index}, ${slot.shot_size}, ${
                gap ? "no clip matched" : "matched"
              }. ${slot.description}`}
              className={clsx(
                "press absolute bottom-0 rounded-[3px] rounded-t-[4px]",
                "focus-visible:outline-offset-4",
              )}
              style={{
                left: `${left + GUTTER / 2}%`,
                width: `calc(${width}% - ${GUTTER}%)`,
                height: `${heightFor(slot) * 100}%`,
                background: gap
                  ? "var(--accent-soft)"
                  : active
                    ? "var(--ink)"
                    : "color-mix(in srgb, var(--ink) 16%, transparent)",
                boxShadow: gap
                  ? `inset 0 0 0 1.5px ${
                      active ? "var(--accent)" : "color-mix(in srgb, var(--accent) 55%, transparent)"
                    }`
                  : "none",
                transition:
                  "background-color var(--t-fast) var(--ease-out), box-shadow var(--t-fast) var(--ease-out), transform var(--t-press) var(--ease-out)",
              }}
            />
          );
        })}
      </div>

      {/* One hairline is enough of a baseline. */}
      <div className="rule mt-0" />
    </div>
  );
}

/** Reads the silhouette for anyone who can't see it. */
export function StripSummary({ template }: { template: Template }) {
  const gaps = template.slots.filter(isGap).length;
  return (
    <p className="sr-only">
      {template.slots.length} shots over {totalBeats(template)} beats,{" "}
      {gaps} of which have no matching clip.
    </p>
  );
}
