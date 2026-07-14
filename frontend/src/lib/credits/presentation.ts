import type { FreeCreditAllowance } from "./types.ts";

const FREE_ALLOWANCE_DURATION_MS = 7 * 24 * 60 * 60 * 1000;

export function creditAllowanceRemainingRatio(
  allowance: Pick<FreeCreditAllowance, "limit" | "remaining">,
): number {
  if (allowance.limit <= 0) return 0;
  return Math.min(
    1,
    Math.max(0, allowance.remaining / allowance.limit),
  );
}

export function projectFreeAllowanceExpiry(now: Date): Date {
  return new Date(now.getTime() + FREE_ALLOWANCE_DURATION_MS);
}

export function formatCreditResetDate(
  expiresAt: string | Date,
  timeZone?: string,
): string {
  return new Intl.DateTimeFormat("ja-JP", {
    month: "long",
    day: "numeric",
    ...(timeZone ? { timeZone } : {}),
  }).format(expiresAt instanceof Date ? expiresAt : new Date(expiresAt));
}
