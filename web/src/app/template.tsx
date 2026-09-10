"use client";

import { motion } from "motion/react";

/**
 * Route enter animation.
 *
 * `template.tsx` re-mounts on every navigation (unlike `layout.tsx`), which is
 * what makes a per-route enter animation possible at all. Kept short and
 * translate-only: it exists to stop two entirely different screens teleporting
 * into each other, not to be noticed.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, transform: "translateY(8px)" }}
      animate={{ opacity: 1, transform: "translateY(0px)" }}
      transition={{ duration: 0.24, ease: [0.23, 1, 0.32, 1] }}
    >
      {children}
    </motion.div>
  );
}
