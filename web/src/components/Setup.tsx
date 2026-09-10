"use client";

import clsx from "clsx";
import { useRef, useState } from "react";

const INPUTS = [
  {
    key: "reference",
    label: "Reference reel",
    hint: "The edit you want to borrow from",
    accept: "video/*",
    multiple: false,
  },
  {
    key: "footage",
    label: "Your footage",
    hint: "Clips and stills to cut from",
    accept: "video/*,image/*",
    multiple: true,
  },
  {
    key: "track",
    label: "Your music",
    hint: "The reference's track can't ship with your reel",
    accept: "audio/*",
    multiple: false,
  },
] as const;

type Counts = Partial<Record<(typeof INPUTS)[number]["key"], number>>;

export default function Setup({ onAnalyze }: { onAnalyze: () => void }) {
  const [counts, setCounts] = useState<Counts>({});
  const ready = INPUTS.every((i) => (counts[i.key] ?? 0) > 0);

  return (
    <div className="mx-auto w-full max-w-[560px]">
      <h1 className="display">
        Cut your footage
        <br />
        like the reel you admire.
      </h1>
      <p className="caption mt-5 max-w-[42ch]">
        Bring an edit you like, your own clips, and your own music. Where nothing
        of yours fits, you&apos;ll get a prompt to generate the missing shot.
      </p>

      <div className="mt-12">
        {INPUTS.map((input, i) => (
          <Row
            key={input.key}
            index={i}
            label={input.label}
            hint={input.hint}
            accept={input.accept}
            multiple={input.multiple}
            count={counts[input.key] ?? 0}
            onPick={(n) => setCounts((c) => ({ ...c, [input.key]: n }))}
          />
        ))}
      </div>

      <div className="mt-10 flex flex-wrap items-center gap-x-4 gap-y-3">
        <button
          onClick={onAnalyze}
          disabled={!ready}
          className={clsx(
            "press rounded-full px-6 py-3 text-[15px] font-medium",
            "disabled:cursor-not-allowed",
          )}
          style={{
            background: ready ? "var(--ink)" : "var(--sunken)",
            color: ready ? "var(--bg)" : "var(--ink-3)",
          }}
        >
          Analyse the reference
        </button>
        {!ready && (
          <span className="caption">Add all three to continue</span>
        )}
      </div>
    </div>
  );
}

function Row({
  index,
  label,
  hint,
  accept,
  multiple,
  count,
  onPick,
}: {
  index: number;
  label: string;
  hint: string;
  accept: string;
  multiple: boolean;
  count: number;
  onPick: (n: number) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const filled = count > 0;

  return (
    <label
      className={clsx(
        "press press-lg hov group flex cursor-pointer items-center gap-4 py-5",
        index > 0 && "rule",
      )}
      style={{ marginInline: "-0.75rem", paddingInline: "0.75rem", borderRadius: 10 }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        className="sr-only"
        onChange={(e) => onPick(e.target.files?.length ?? 0)}
      />

      {/* State is carried by one small mark rather than a badge, a border and
          a colour all saying the same thing. */}
      <span
        aria-hidden
        className="grid h-6 w-6 shrink-0 place-items-center rounded-full"
        style={{
          border: filled ? "none" : "1px solid var(--line-2)",
          background: filled ? "var(--ink)" : "transparent",
          transition: "background-color var(--t-fast) var(--ease-out)",
        }}
      >
        {filled && (
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path
              d="M2.5 6.2 4.8 8.5 9.5 3.8"
              stroke="var(--bg)"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </span>

      <span className="min-w-0 flex-1">
        <span className="body block font-medium">{label}</span>
        <span className="caption block truncate">
          {filled
            ? `${count} file${count > 1 ? "s" : ""} selected`
            : hint}
        </span>
      </span>

      <span className="micro shrink-0" style={{ color: "var(--ink-3)" }}>
        {filled ? "Change" : "Choose"}
      </span>
    </label>
  );
}
