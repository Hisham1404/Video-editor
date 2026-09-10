"use client";

import { useEffect, useState } from "react";
import { STAGES } from "@/lib/template";

const STEP_MS = 460;

/**
 * The analysis run.
 *
 * Seen once per job, so this is where the delight budget belongs — but it is
 * still a progress view, not a show: it tells you which stage is running and
 * what that stage costs you. The metered stage is marked, because cost per job
 * is a number this project tracks rather than hides.
 */
export default function Analysing({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(0);

  // `onDone` must be stable in the parent, or every re-render restarts the
  // timer. It is, so it can just be a dependency instead of a ref shim.
  useEffect(() => {
    if (step >= STAGES.length) {
      const t = setTimeout(onDone, 420);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setStep((s) => s + 1), STEP_MS);
    return () => clearTimeout(t);
  }, [step, onDone]);

  const pct = Math.min(100, (step / STAGES.length) * 100);

  return (
    <div className="mx-auto w-full max-w-[420px] py-4 text-center">
      <h1 className="title">Reading the reference</h1>
      <p className="caption mx-auto mt-1 max-w-[36ch]">
        Shot boundaries, then rhythm, then what each shot is doing.
      </p>

      {/* One hairline that fills.
          scaleX, not width: width triggers layout on every frame, transform
          runs on the compositor. Linear, because constant motion should be
          linear — an eased progress bar lies about the rate. */}
      <div
        className="mt-8 h-px w-full overflow-hidden"
        style={{ background: "var(--line)" }}
      >
        <div
          className="h-full w-full origin-left"
          style={{
            transform: `scaleX(${pct / 100})`,
            background: "var(--ink)",
            transition: `transform ${STEP_MS}ms linear`,
          }}
        />
      </div>

      <ol className="mt-8">
        {STAGES.map((s, i) => {
          const state = i < step ? "done" : i === step ? "running" : "waiting";
          return (
            <li
              key={s.n}
              className="flex items-center justify-center gap-2.5 py-2.5"
              style={{
                opacity: state === "waiting" ? 0.32 : 1,
                transition: "opacity var(--t-base) var(--ease-out)",
              }}
            >
              <Mark state={state} />
              <span className="body">{s.name}</span>
              {s.metered && (
                <span className="micro" style={{ color: "var(--accent)" }}>
                  metered
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function Mark({ state }: { state: "done" | "running" | "waiting" }) {
  return (
    <span
      aria-hidden
      className="grid h-[18px] w-[18px] shrink-0 place-items-center rounded-full"
      style={{
        border: state === "done" ? "none" : "1px solid var(--line-2)",
        background: state === "done" ? "var(--ink)" : "transparent",
        transition: "background-color var(--t-fast) var(--ease-out)",
      }}
    >
      {state === "done" && (
        <svg width="10" height="10" viewBox="0 0 12 12" fill="none">
          <path
            d="M2.5 6.2 4.8 8.5 9.5 3.8"
            stroke="var(--bg)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )}
      {state === "running" && (
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{
            background: "var(--ink)",
            animation: "pulse 1.1s ease-in-out infinite",
          }}
        />
      )}
      <style>{`@keyframes pulse{0%,100%{opacity:.35}50%{opacity:1}}`}</style>
    </span>
  );
}
