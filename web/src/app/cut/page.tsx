"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";
import Result from "@/components/Result";
import Shell from "@/components/Shell";
import { MOCK_TEMPLATE } from "@/lib/template";

export default function CutPage() {
  const router = useRouter();
  const restart = useCallback(() => router.push("/new"), [router]);
  return (
    <Shell step={3} back="/">
      <Result template={MOCK_TEMPLATE} onRestart={restart} />
    </Shell>
  );
}
