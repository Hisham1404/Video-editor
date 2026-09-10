"use client";

import Link from "next/link";
import { washStyle } from "@/components/Frame";
import { PROJECTS, formatWhen } from "@/lib/projects";

/**
 * Where you land.
 *
 * Previously the app opened straight into a file picker, which assumes every
 * visit is a new job. Most aren't — you come back to something you already
 * started. So: start a new cut, or reopen one.
 *
 * No "⋮" menus on the rows. A control that opens nothing is worse than no
 * control, and rename/duplicate/delete need the API layer that doesn't exist
 * yet.
 */
export default function Home() {
  return (
    <div className="mx-auto w-full max-w-[520px] text-center">
      <h1 className="title">Reel Editor</h1>
      <p className="caption mt-1">
        {PROJECTS.length} projects
      </p>

      {/* Primary action. One card, not a row of three — we do one thing. */}
      <Link
        href="/new"
        className="press press-lg hov mt-8 flex flex-col items-center gap-3 rounded-[14px] p-6"
        style={{ border: "1px solid var(--line)" }}
      >
        <span
          aria-hidden
          className="grid h-12 w-12 place-items-center rounded-full"
          style={{ background: "var(--ink)" }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path
              d="M12 5v14M5 12h14"
              stroke="var(--bg)"
              strokeWidth="1.8"
              strokeLinecap="round"
            />
          </svg>
        </span>
        <span>
          <span className="body block font-medium">Start a new cut</span>
          <span className="caption mt-0.5 block">
            A reference reel, your footage, a track
          </span>
        </span>
      </Link>

      <section className="mt-12">
        <h2 className="eyebrow">Recent</h2>

        {/* The list is centred as a block, but the rows inside stay aligned to
            each other. Centring each row individually makes every thumbnail
            start at a different x — a ragged edge that reads as broken, not
            as centred. */}
        <ul className="mx-auto mt-4 w-fit text-left">
          {PROJECTS.map((p, i) => (
            <li key={p.id}>
              <Link
                href="/cut"
                className="press press-lg hov flex items-center gap-3.5 py-4"
                style={{
                  borderTop: i === 0 ? undefined : "1px solid var(--line)",
                  marginInline: "-0.75rem",
                  paddingInline: "0.75rem",
                  borderRadius: 10,
                }}
              >
                <span
                  aria-hidden
                  className="h-12 w-9 shrink-0"
                  style={{ ...washStyle(p.seed), borderRadius: 6 }}
                />
                <span className="text-left">
                  <span className="body block font-medium">{p.name}</span>
                  <span className="caption block">
                    {formatWhen(p.updatedAt)} ·{" "}
                    <span className="num">{p.shots}</span> shots
                    {p.gaps > 0 && (
                      <>
                        {" · "}
                        <span className="num" style={{ color: "var(--accent)" }}>
                          {p.gaps}
                        </span>{" "}
                        to generate
                      </>
                    )}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
