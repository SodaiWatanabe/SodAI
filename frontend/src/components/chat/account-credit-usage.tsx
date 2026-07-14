"use client";

import { useEffect } from "react";

import { useCreditBalance } from "@/components/credits/credit-balance-provider";
import { FreeCreditAllowanceMeter } from "@/components/credits/free-credit-allowance-meter";
import { PopoverClose } from "@/components/ui/popover";

type AccountCreditUsageProps = {
  active: boolean;
  onOpenCredits: () => void;
};

export function AccountCreditUsage({
  active,
  onOpenCredits,
}: AccountCreditUsageProps) {
  const {
    balance,
    failed,
    loading,
    refreshBalance,
  } = useCreditBalance();

  useEffect(() => {
    if (active) void refreshBalance();
  }, [active, refreshBalance]);

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
              onClick={() => void refreshBalance()}
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

  return (
    <div className="min-w-0">
      <PopoverClose
        className="w-full rounded-xl px-2.5 py-2 text-left transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
        onClick={onOpenCredits}
      >
        <div className="min-w-0">
          <FreeCreditAllowanceMeter balance={balance} />
          <span className="sr-only">クレジット設定を開く</span>
        </div>
      </PopoverClose>
      {failed ? (
        <div className="flex items-center justify-between gap-2 px-2.5 pb-1 text-xs">
          <span role="status" aria-live="polite" className="text-[var(--muted)]">
            更新できませんでした
          </span>
          <button
            type="button"
            aria-label="クレジット利用状況を再読み込み"
            className="font-medium text-[var(--text)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
            onClick={() => void refreshBalance()}
          >
            再試行
          </button>
        </div>
      ) : null}
    </div>
  );
}
