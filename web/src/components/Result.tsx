"use client";

import { useState } from "react";
import Strip, { StripSummary } from "@/components/Strip";
import ShotDetail from "@/components/ShotDetail";
import Tempo from "@/components/Tempo";
import {
  MOCK_METRICS,
  type Template,
  formatSeconds,
  isGap,
  totalSeconds,
} from "@/lib/template";

export default function Result({
  template,
  onRestart,
}: {
  template: Template;
  onRestart: () => void;
}) {
  const [bpm, setBpm] = useState(112);
  const [selected, setSelected] = useState<number | null>(null);

  const slot =
    selected === null
      ? null
      : (template.slots.find((s) => s.index === selected) ?? null);
  const gaps = template.slots.filter(isGap);

  return (
    <div className="mx-auto w-full max-w-[720px]">
      <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <h1 className="title">Your cut</h1>
          <p className="caption mt-1 num">
            {template.slots.length} shots · {formatSeconds(totalSeconds(template, bpm))}
            {gaps.length > 0 && (
              <>
                {" · "}
                <span style={{ color: "var(--accent)" }}>
                  {gaps.length} to generate
                </span>
              </>
            )}
          </p>
        </div>
        <button
          disabled
          title="Render is stage 8, which isn't implemented yet"
          className="press rounded-full px-5 py-2.5 text-[14px] font-medium disabled:cursor-not-allowed disabled:opacity-35"
          style={{ background: "var(--ink)", color: "var(--bg)" }}
        >
          Render
        </button>
      </header>

      <div className="mt-8">
        <Strip template={template} selected={selected} onSelect={setSelected} />
        <StripSummary template={template} />
      </div>

      <div className="mt-6">
        <ShotDetail
          slot={slot}
          bpm={bpm}
          matched={template.slots.length - gaps.length}
          gaps={gaps.length}
        />
      </div>

      {gaps.length > 0 && (
        <section className="rule mt-8 pt-8">
          <h2 className="title">Shots to generate</h2>
          <p className="caption mt-1 max-w-[46ch]">
            Nothing of yours fits these. Take the prompt to a video model and
            bring the clip back — generation never runs in here.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {gaps.map((g) => (
              <button
                key={g.index}
                onClick={() => setSelected(g.index)}
                className="press hov rounded-full px-3.5 py-1.5 text-[13px]"
                style={{
                  border: "1px solid",
                  borderColor:
                    selected === g.index ? "var(--accent)" : "var(--line-2)",
                  color: "var(--accent)",
                }}
              >
                Shot {g.index + 1} · {g.shot_size}
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="rule mt-8 pt-8">
        <Tempo bpm={bpm} onChange={setBpm} referenceBpm={template.reference_bpm} />
      </section>

      <footer className="rule mt-10 pt-6">
        <p className="micro num">
          ${MOCK_METRICS.costUsd.toFixed(4)} per job ·{" "}
          {MOCK_METRICS.p95LatencyS.toFixed(2)}s p95 · {MOCK_METRICS.model}
        </p>
        <p className="micro mt-2 max-w-[62ch]">
          Cut timings are stored as beat index, subdivision and phrase position.
          The seconds above are derived from your tempo and appear nowhere in
          the template — which is why the same cut can move to any track.
        </p>
        <button
          onClick={onRestart}
          className="press micro mt-4 underline underline-offset-4"
          style={{ color: "var(--ink-2)" }}
        >
          Start over
        </button>
      </footer>
    </div>
  );
}
