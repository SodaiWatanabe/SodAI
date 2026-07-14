import type { CreditBalance } from "@/lib/credits/types";
import {
  formatCreditResetDate,
  presentFreeCreditAllowance,
} from "@/lib/credits/presentation";

export function FreeCreditAllowanceMeter({
  balance,
  className = "",
  variant = "compact",
}: {
  balance: CreditBalance;
  className?: string;
  variant?: "compact" | "settings";
}) {
  const { remainingPercent, resetAt } = presentFreeCreditAllowance(
    balance.free_allowance,
    new Date(),
  );
  const compact = variant === "compact";

  return (
    <div className={className}>
      <div
        className={`flex min-w-0 items-baseline justify-between gap-3 ${compact ? "text-xs" : "text-sm"}`}
      >
        <span className="font-medium text-[var(--text)]">
          今週のクレジット
        </span>
        <span className="shrink-0 tabular-nums text-[var(--muted)]">
          {remainingPercent}%
        </span>
      </div>
      <div
        role="progressbar"
        aria-label="今週のクレジット残量"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={remainingPercent}
        aria-valuetext={`残量 ${remainingPercent}%`}
        className={`${compact ? "mt-2" : "mt-3"} h-1.5 overflow-hidden rounded-full bg-[var(--control-background)]`}
      >
        <div
          className="h-full rounded-full bg-[var(--primary)] transition-[width] duration-300 motion-reduce:transition-none"
          style={{ width: `${remainingPercent}%` }}
        />
      </div>
      <p className="mt-1.5 text-xs tabular-nums text-[var(--muted)]">
        {formatCreditResetDate(resetAt)}に利用枠がリセットされます
      </p>
    </div>
  );
}
