"use client";

import NumberFlow from "@number-flow/react";
import { useCallback, useRef, useState } from "react";

const MIN = 60;
const MAX = 180;

/** Past the end, the value follows less the further you push. Real things
 *  slow before they stop; a hard clamp reads as frozen. */
function rubberband(overshoot: number, dimension: number, c = 0.55) {
  return (overshoot * dimension * c) / (dimension + c * Math.abs(overshoot));
}

interface Props {
  bpm: number;
  onChange: (bpm: number) => void;
  referenceBpm: number | null;
}

/**
 * Tempo, dragged rather than typed, because the point is to feel the cut
 * re-time under your finger. Tracks the pointer 1:1, resists past either end,
 * and settles back on release. The figure is animated per-digit — it is the
 * one number on the page that changes continuously, so it earns the motion.
 */
export default function Tempo({ bpm, onChange, referenceBpm }: Props) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);
  const [overshoot, setOvershoot] = useState(0);

  const pct = ((bpm - MIN) / (MAX - MIN)) * 100;

  const read = useCallback((clientX: number) => {
    const el = trackRef.current;
    if (!el) return { value: bpm, over: 0 };
    const r = el.getBoundingClientRect();
    const raw = MIN + ((clientX - r.left) / r.width) * (MAX - MIN);
    const value = Math.min(MAX, Math.max(MIN, Math.round(raw)));
    let over = 0;
    if (raw < MIN) over = -rubberband(((MIN - raw) / (MAX - MIN)) * r.width, r.width);
    else if (raw > MAX) over = rubberband(((raw - MAX) / (MAX - MIN)) * r.width, r.width);
    return { value, over };
  }, [bpm]);

  const down = (e: React.PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    setDragging(true);
    const { value, over } = read(e.clientX);
    setOvershoot(over);
    if (value !== bpm) onChange(value);
  };

  const move = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging) return;
    const { value, over } = read(e.clientX);
    setOvershoot(over);
    if (value !== bpm) onChange(value);
  };

  const up = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging) return;
    if (e.currentTarget.hasPointerCapture(e.pointerId))
      e.currentTarget.releasePointerCapture(e.pointerId);
    setDragging(false);
    setOvershoot(0);
  };

  const key = (e: React.KeyboardEvent) => {
    const step = e.shiftKey ? 10 : 1;
    let next = bpm;
    if (e.key === "ArrowLeft" || e.key === "ArrowDown") next = bpm - step;
    else if (e.key === "ArrowRight" || e.key === "ArrowUp") next = bpm + step;
    else if (e.key === "Home") next = MIN;
    else if (e.key === "End") next = MAX;
    else return;
    e.preventDefault();
    onChange(Math.min(MAX, Math.max(MIN, next)));
  };

  return (
    <section>
      <div className="mb-4 flex items-end justify-between gap-6">
        <div className="min-w-0">
          <h2 className="title">Your tempo</h2>
          <p className="caption mt-1">
            {referenceBpm
              ? `The reference was cut at ${referenceBpm} BPM`
              : "The track you're cutting to"}
          </p>
        </div>
        <div className="flex shrink-0 items-baseline gap-1.5">
          <NumberFlow
            value={bpm}
            className="num text-[2.5rem] font-semibold leading-none tracking-[-0.035em] sm:text-[3rem]"
            transformTiming={{ duration: 320, easing: "cubic-bezier(0.23,1,0.32,1)" }}
          />
          <span className="micro pb-1">BPM</span>
        </div>
      </div>

      <div
        ref={trackRef}
        role="slider"
        tabIndex={0}
        aria-label="Tempo in beats per minute"
        aria-valuemin={MIN}
        aria-valuemax={MAX}
        aria-valuenow={bpm}
        aria-valuetext={`${bpm} beats per minute`}
        onPointerDown={down}
        onPointerMove={move}
        onPointerUp={up}
        onPointerCancel={up}
        onKeyDown={key}
        className="relative -my-3 cursor-grab touch-none select-none py-3 active:cursor-grabbing"
        style={{
          transform: `translateX(${overshoot}px)`,
          transition: dragging ? "none" : "transform var(--t-base) var(--ease-out)",
        }}
      >
        <div className="h-px w-full" style={{ background: "var(--line-2)" }} />
        {/* `left` is never transitioned. During a drag it must track the
            pointer with no lag at all, and the only other way it changes is
            arrow keys — a keyboard-initiated action, which should never
            animate. Only the press scale animates. */}
        <div
          className="absolute top-1/2 h-3 w-3 rounded-full"
          style={{
            left: `${pct}%`,
            background: "var(--ink)",
            transform: `translate(-50%, -50%) scale(${dragging ? 1.35 : 1})`,
            transition: "transform var(--t-press) var(--ease-out)",
          }}
        />
      </div>

      <div className="mt-3 flex justify-between">
        <span className="micro num">{MIN}</span>
        <span className="micro">Drag to re-time the cut</span>
        <span className="micro num">{MAX}</span>
      </div>
    </section>
  );
}
