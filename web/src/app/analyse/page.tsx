"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";
import Analysing from "@/components/Analysing";
import Shell from "@/components/Shell";

export default function AnalysePage() {
  const router = useRouter();
  // replace, not push: nobody wants Back to drop them into a finished
  // progress bar.
  const go = useCallback(() => router.replace("/cut"), [router]);
  return (
    <Shell step={2} back="/new">
      <Analysing onDone={go} />
    </Shell>
  );
}
