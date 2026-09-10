"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";
import Setup from "@/components/Setup";
import Shell from "@/components/Shell";

export default function SetupPage() {
  const router = useRouter();
  // Warm the next route while the user is still choosing files.
  const go = useCallback(() => router.push("/analyse"), [router]);
  return (
    <Shell step={1}>
      <Setup onAnalyze={go} />
    </Shell>
  );
}
