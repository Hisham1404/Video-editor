"use client";

import Link from "next/link";

const STEPS = ["Sources", "Reading", "Your cut"] as const;

/**
 * Page chrome: where you are, and how to get back.
 *
 * Every screen should answer "where am I?" and "how do I get out?". The old
 * version answered neither — all three screens lived at one URL with no way
 * back except finishing the flow.
 *
 * The step marker is three rules rather than numbered circles: it reads as
 * progress at a glance and adds no chrome to argue with the content.
 */
export default function Shell({
  step,
  back,
  children,
}: {
  step: 1 | 2 | 3;
  back?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mx-auto w-full max-w-[900px] px-5 py-6 sm:px-8 sm:py-8">
      <nav
        aria-label="Progress"
        className="relative mb-10 flex items-center justify-center sm:mb-14"
      >
        {back ? (
          <Link
            href={back}
            className="press micro absolute left-0 top-1/2 inline-flex -translate-y-1/2 items-center gap-1.5"
            style={{ color: "var(--ink-2)" }}
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
              <path
                d="M10 3 5 8l5 5"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Back
          </Link>
        ) : (
          <span
            className="micro absolute left-0 top-1/2 -translate-y-1/2"
            style={{ color: "var(--ink-3)" }}
          >
            Reel Editor
          </span>
        )}

        <ol className="flex items-center gap-2">
          {STEPS.map((label, i) => {
            const n = i + 1;
            const state = n < step ? "done" : n === step ? "current" : "todo";
            return (
              <li key={label} className="flex items-center gap-2">
                <span
                  className="micro hidden sm:inline"
                  style={{
                    color:
                      state === "current" ? "var(--ink)" : "var(--ink-3)",
                    fontWeight: state === "current" ? 590 : undefined,
                  }}
                  aria-current={state === "current" ? "step" : undefined}
                >
                  {label}
                </span>
                <span
                  aria-hidden
                  className="block h-px w-6 sm:w-8"
                  style={{
                    background:
                      state === "todo" ? "var(--line)" : "var(--ink)",
                    opacity: state === "done" ? 0.35 : 1,
                  }}
                />
              </li>
            );
          })}
          <li className="sr-only">
            Step {step} of {STEPS.length}: {STEPS[step - 1]}
          </li>
        </ol>
      </nav>

      <main id="content">{children}</main>
    </div>
  );
}
