"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";
import Analysing from "@/components/Analysing";
import Shell from "@/components/Shell";

export default function AnalysePage() {
  const router = useRouter();
  const go = useCallback(() => router.replace("/cut"), [router]);
  // replace, not push: nobody wants Back to drop them into a finished
  // progress bar.
  return (
    <Shell step={2} back="/">
      <Analysing onDone={go} />
    </Shell>
  );
}
