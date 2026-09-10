"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";
import Setup from "@/components/Setup";
import Shell from "@/components/Shell";

export default function NewCutPage() {
  const router = useRouter();
  const go = useCallback(() => router.push("/analyse"), [router]);
  return (
    <Shell step={1} back="/">
      <Setup onAnalyze={go} />
    </Shell>
  );
}
