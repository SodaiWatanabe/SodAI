"use client";

import { useEffect, useState } from "react";

function remainingSeconds(deadlineAt: string, now: number): number {
  return Math.max(0, Math.ceil((Date.parse(deadlineAt) - now) / 1000));
}

function formatRemainingTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}:${String(remainder).padStart(2, "0")}`;
}

export function BrainAssignmentDeadline({ deadlineAt }: { deadlineAt: string }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [deadlineAt]);

  const remaining = remainingSeconds(deadlineAt, now);
  const breathing = remaining > 0 && remaining <= 60;

  return (
    <p
      role="timer"
      aria-label={`残り時間${formatRemainingTime(remaining)}`}
      className="flex h-full shrink-0 items-center px-2.5"
    >
      <span
        aria-hidden="true"
        className={`brain-deadline-time block text-sm font-medium leading-none tabular-nums text-[var(--text)] ${
          breathing ? "brain-deadline-time-breathing" : ""
        }`}
      >
        {formatRemainingTime(remaining)}
      </span>
    </p>
  );
}
