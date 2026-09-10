"use client";

import { toast } from "sonner";
import {
  type Slot,
  durationBeats,
  durationSeconds,
  isGap,
} from "@/lib/template";

/**
 * The selected shot, inline.
 *
 * Deliberately not a modal: there is room for it on every size, so covering
 * the cut to describe one shot of it would be a worse trade. Nothing to
 * dismiss, nothing to trap you.
 */
export default function ShotDetail({
  slot,
  bpm,
  matched,
  gaps,
}: {
  slot: Slot | null;
  bpm: number;
  matched: number;
  gaps: number;
}) {
  /**
   * No AnimatePresence here, deliberately.
   *
   * Selecting a shot happens tens of times in a session, which is the tier
   * where motion should be near-imperceptible or absent. And `mode="wait"`
   * gates the incoming content on the outgoing exit animation — so if
   * requestAnimationFrame is throttled (a backgrounded tab, a busy main
   * thread) the panel silently stops updating while the rest of the page
   * keeps working. Content should never be hostage to a decoration.
   *
   * The keyed CSS animation below is pure decoration: the text is in the DOM
   * immediately either way.
   */
  return (
    <div className="min-h-[104px]">
      {slot ? (
        <div key={slot.index} className="rise">
          <Body slot={slot} bpm={bpm} />
        </div>
      ) : (
          /* Reserving a block for the detail and then filling it with
             "select something" wastes the space. Say what the strip above
             actually shows instead. */
          <div>
            <p className="eyebrow">The cut so far</p>
            <p className="body mx-auto mt-2 max-w-[52ch]">
              <span className="num">{matched}</span> shots came from your
              footage
              {gaps > 0 && (
                <>
                  {", "}
                  <span className="num" style={{ color: "var(--accent)" }}>
                    {gaps}
                  </span>{" "}
                  still need generating
                </>
              )}
              .
            </p>
            <p className="caption mt-1">
              Pick a shot from the strip to see what it is.
            </p>
          </div>
        )}
    </div>
  );
}

function Body({ slot, bpm }: { slot: Slot; bpm: number }) {
  const gap = isGap(slot);

  return (
    <>
      <div className="flex flex-wrap items-baseline justify-center gap-x-2 gap-y-1">
        <span className="eyebrow">Shot {slot.index + 1}</span>
        {gap && (
          <span className="eyebrow" style={{ color: "var(--accent)" }}>
            · no clip matched
          </span>
        )}
      </div>

      <p className="title mt-2">{slot.description}</p>

      <p className="caption mt-2">
        {[
          slot.shot_size,
          slot.framing,
          slot.camera_motion,
          `${durationBeats(slot)} beats`,
          `${durationSeconds(slot, bpm).toFixed(2)}s at ${bpm} BPM`,
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>

      {gap && slot.generation_prompt && (
        <div className="mt-4">
          <p
            className="body rounded-lg p-3"
            style={{ background: "var(--accent-soft)", color: "var(--ink)" }}
          >
            {slot.generation_prompt}
          </p>
          <div className="mt-3 flex flex-wrap justify-center gap-2">
            <CopyButton text={slot.generation_prompt} />
            <label className="press hov rounded-full px-4 py-2 text-[13px] font-medium" style={{ border: "1px solid var(--line-2)" }}>
              <span className="cursor-pointer">Upload the clip</span>
              <input type="file" accept="video/*" className="sr-only" />
            </label>
          </div>
        </div>
      )}
    </>
  );
}

/**
 * Copy, with the failure path handled.
 *
 * navigator.clipboard throws NotAllowedError wherever clipboard-write is
 * denied, so this falls back to execCommand and finally to selecting the text.
 * The result is announced through a toast rather than by mutating the button's
 * own label — the button should still say what it does after you've pressed it.
 */
function CopyButton({ text }: { text: string }) {
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Prompt copied");
      return;
    } catch {
      /* denied — fall through */
    }
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.cssText = "position:fixed;top:0;left:0;opacity:0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      if (ok) {
        toast.success("Prompt copied");
        return;
      }
    } catch {
      /* fall through */
    }
    toast("Copying is blocked here", {
      description: "Select the prompt text and copy it manually.",
    });
  }

  return (
    <button
      onClick={copy}
      className="press rounded-full px-4 py-2 text-[13px] font-medium"
      style={{ background: "var(--ink)", color: "var(--bg)" }}
    >
      Copy prompt
    </button>
  );
}
