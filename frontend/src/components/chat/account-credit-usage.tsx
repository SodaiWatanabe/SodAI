"use client";

import { useEffect, useState } from "react";

import type { CreditBalance } from "@/lib/credits/types";
import {
  creditAllowanceRemainingRatio,
  formatCreditResetDate,
  projectFreeAllowanceExpiry,
} from "@/lib/credits/presentation";
import { useCreditsApi } from "@/lib/credits/use-credits-api";

type AccountCreditUsageProps = {
  active: boolean;
  onRetry: () => void;
  requestVersion: number;
};

type CreditLoadResult = {
  balance?: CreditBalance;
  failed: boolean;
  version: number;
};

export function AccountCreditUsage({
  active,
  onRetry,
  requestVersion,
}: AccountCreditUsageProps) {
  const creditsApi = useCreditsApi();
  const [result, setResult] = useState<CreditLoadResult>({
    failed: false,
    version: 0,
  });

  useEffect(() => {
    if (!active || requestVersion === 0) return;
    let cancelled = false;
    void creditsApi.getBalance().then(
      (nextBalance) => {
        if (cancelled) return;
        setResult({ balance: nextBalance, failed: false, version: requestVersion });
      },
      () => {
        if (cancelled) return;
        setResult((current) => ({
          balance: current.balance,
          failed: true,
          version: requestVersion,
        }));
      },
    );
    return () => {
      cancelled = true;
    };
  }, [active, creditsApi, requestVersion]);

  const loading = active && result.version !== requestVersion;
  const failed = !loading && result.failed;
  const balance = result.balance;

  if (!balance) {
    return (
      <div className="px-2.5 py-2.5 text-xs text-[var(--muted)]">
        {failed ? (
          <div className="flex items-center justify-between gap-3">
            <span role="status" aria-live="polite">
              利用状況を読み込めませんでした。
            </span>
            <button
              type="button"
              aria-label="クレジット利用状況を再読み込み"
              className="shrink-0 font-medium text-[var(--text)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
              onClick={onRetry}
            >
              再試行
            </button>
          </div>
        ) : (
          <span aria-live="polite">
            {loading ? "利用状況を読み込み中…" : "利用状況"}
          </span>
        )}
      </div>
    );
  }

  const allowance = balance.free_allowance;

  if (!allowance) {
    const projectedResetDate = formatCreditResetDate(
      projectFreeAllowanceExpiry(new Date()),
    );
    return (
      <div className="min-w-0 px-2.5 py-2">
        <div className="flex min-w-0 items-baseline justify-between gap-3 text-xs">
          <span className="font-medium text-[var(--text)]">無料クレジット</span>
          <span className="shrink-0 tabular-nums text-[var(--muted)]">100%</span>
        </div>
        <div
          role="progressbar"
          aria-label="無料クレジット残量"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={100}
          aria-valuetext="残量 100%"
          className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--control-background)]"
        >
          <div className="h-full w-full rounded-full bg-[var(--primary)]" />
        </div>
        <p className="mt-1.5 text-xs text-[var(--muted)]">
          {projectedResetDate}にリセットされます
        </p>
        {failed ? (
          <div className="mt-1.5 flex items-center justify-between gap-2 text-xs">
            <span role="status" aria-live="polite" className="text-[var(--muted)]">
              更新できませんでした
            </span>
            <button
              type="button"
              aria-label="クレジット利用状況を再読み込み"
              className="font-medium text-[var(--text)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
              onClick={onRetry}
            >
              再試行
            </button>
          </div>
        ) : null}
      </div>
    );
  }

  const remainingRatio = creditAllowanceRemainingRatio(allowance);
  const remainingPercent = Math.round(remainingRatio * 100);

  return (
    <div className="min-w-0 px-2.5 py-2">
      <div className="flex min-w-0 items-baseline justify-between gap-3 text-xs">
        <span className="font-medium text-[var(--text)]">無料クレジット</span>
        <span className="shrink-0 tabular-nums text-[var(--muted)]">
          {remainingPercent}%
        </span>
      </div>
      <div
        role="progressbar"
        aria-label="無料クレジット残量"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={remainingPercent}
        aria-valuetext={`残量 ${remainingPercent}%`}
        className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--control-background)]"
      >
        <div
          className="h-full rounded-full bg-[var(--primary)] transition-[width] duration-300 motion-reduce:transition-none"
          style={{ width: `${remainingPercent}%` }}
        />
      </div>
      <div className="mt-1.5 flex min-w-0 items-center justify-between gap-2 text-xs text-[var(--muted)]">
        <span className="truncate tabular-nums">
          {formatCreditResetDate(allowance.expires_at)}にリセットされます
        </span>
        {failed ? (
          <span role="status" aria-live="polite" className="shrink-0">
            更新できませんでした
          </span>
        ) : null}
      </div>
      {failed ? (
        <button
          type="button"
          aria-label="クレジット利用状況を再読み込み"
          className="mt-1.5 text-xs font-medium text-[var(--text)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
          onClick={onRetry}
        >
          再試行
        </button>
      ) : null}
    </div>
  );
}
