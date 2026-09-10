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
    <div className="mx-auto w-full max-w-[720px]">
      <header className="flex items-baseline justify-between gap-4">
        <h1 className="title">Reel Editor</h1>
        <span className="micro">{PROJECTS.length} projects</span>
      </header>

      {/* Primary action. One card, not a row of three — we do one thing. */}
      <Link
        href="/new"
        className="press press-lg hov mt-6 flex items-center gap-4 rounded-[14px] p-4 sm:gap-5 sm:p-5"
        style={{ border: "1px solid var(--line)" }}
      >
        <span
          aria-hidden
          className="grid h-14 w-14 shrink-0 place-items-center rounded-[10px] sm:h-16 sm:w-16"
          style={{ background: "var(--ink)" }}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <path
              d="M12 5v14M5 12h14"
              stroke="var(--bg)"
              strokeWidth="1.7"
              strokeLinecap="round"
            />
          </svg>
        </span>
        <span className="min-w-0">
          <span className="body block font-medium">Start a new cut</span>
          <span className="caption block">
            Bring a reference reel, your footage and a track
          </span>
        </span>
      </Link>

      <section className="mt-10">
        <h2 className="eyebrow">Recent</h2>

        <ul className="mt-3">
          {PROJECTS.map((p, i) => (
            <li key={p.id}>
              <Link
                href="/cut"
                className="press press-lg hov flex items-center gap-4 py-3.5"
                style={{
                  borderTop: i === 0 ? undefined : "1px solid var(--line)",
                  marginInline: "-0.75rem",
                  paddingInline: "0.75rem",
                  borderRadius: 10,
                }}
              >
                <span
                  aria-hidden
                  className="h-14 w-10 shrink-0 rounded-md sm:h-16 sm:w-11"
                  style={{ ...washStyle(p.seed), borderRadius: 6 }}
                />
                <span className="min-w-0 flex-1">
                  <span className="body block truncate font-medium">
                    {p.name}
                  </span>
                  <span className="caption block truncate">
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
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 16 16"
                  fill="none"
                  aria-hidden
                  className="shrink-0"
                  style={{ color: "var(--ink-3)" }}
                >
                  <path
                    d="m6 3 5 5-5 5"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
