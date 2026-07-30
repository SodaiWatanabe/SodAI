"use client";

import { useEffect, useState } from "react";

import { reasoningEffortName } from "@/lib/chat/reasoning-effort";
import type { ReasoningEffort } from "@/lib/chat/types";

function remainingSeconds(deadlineAt: string, now: number): number {
  return Math.max(0, Math.ceil((Date.parse(deadlineAt) - now) / 1000));
}

function formatRemainingTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}:${String(remainder).padStart(2, "0")}`;
}

export function BrainAssignmentDeadline({
  deadlineAt,
  reasoningEffort,
}: {
  deadlineAt: string;
  reasoningEffort: ReasoningEffort;
}) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [deadlineAt]);

  const remaining = remainingSeconds(deadlineAt, now);

  return (
    <p
      role="timer"
      aria-label={`思考の深さ${reasoningEffortName(reasoningEffort)}、残り${formatRemainingTime(remaining)}`}
      className="shrink-0 px-2.5 text-xs tabular-nums text-[var(--muted)]"
    >
      思考 {reasoningEffortName(reasoningEffort)}
      <span aria-hidden="true"> · </span>
      残り {formatRemainingTime(remaining)}
    </p>
  );
}
