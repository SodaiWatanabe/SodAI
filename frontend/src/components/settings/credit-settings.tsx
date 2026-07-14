"use client";

import { useEffect, useRef, useState } from "react";

import { useCreditBalance } from "@/components/credits/credit-balance-provider";
import { FreeCreditAllowanceMeter } from "@/components/credits/free-credit-allowance-meter";
import { IOSSpinner } from "@/components/ui/ios-spinner";
import {
  formatCreditAmount,
  formatCreditTransactionDate,
  presentCreditTransaction,
} from "@/lib/credits/presentation";
import type {
  CreditTransaction,
  CreditTransactionPage,
} from "@/lib/credits/types";
import { useCreditsApi } from "@/lib/credits/use-credits-api";

type CreditHistoryState = CreditTransactionPage & {
  failed: boolean;
  loadingMore: boolean;
  version: number;
};

const EMPTY_HISTORY: CreditHistoryState = {
  failed: false,
  items: [],
  loadingMore: false,
  next_cursor: null,
  version: 0,
};

function CreditHistoryItem({
  scale,
  transaction,
}: {
  scale: number;
  transaction: CreditTransaction;
}) {
  const presentation = presentCreditTransaction(transaction);
  const showPositiveSign = presentation.tone === "increase";

  return (
    <li className="flex min-h-14 items-center gap-4 border-t border-[var(--separator)] first:border-t-0">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-[var(--text)]">
          {presentation.label}
        </p>
        <p className="mt-0.5 text-xs tabular-nums text-[var(--muted)]">
          {formatCreditTransactionDate(transaction.created_at)}
        </p>
      </div>
      <span
        className={`shrink-0 text-sm tabular-nums ${
          presentation.tone === "neutral"
            ? "text-[var(--muted)]"
            : "text-[var(--text)]"
        }`}
      >
        {formatCreditAmount(
          presentation.amount,
          scale,
          showPositiveSign,
        )}
      </span>
    </li>
  );
}

export function CreditSettings() {
  const creditsApi = useCreditsApi();
  const {
    balance,
    failed: balanceFailed,
    refreshBalance,
  } = useCreditBalance();
  const mountedRef = useRef(true);
  const [historyVersion, setHistoryVersion] = useState(1);
  const [history, setHistory] = useState<CreditHistoryState>(EMPTY_HISTORY);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    void refreshBalance();
  }, [refreshBalance]);

  useEffect(() => {
    let cancelled = false;
    void creditsApi.getTransactions().then(
      (page) => {
        if (cancelled) return;
        setHistory({
          ...page,
          failed: false,
          loadingMore: false,
          version: historyVersion,
        });
      },
      () => {
        if (cancelled) return;
        setHistory((current) => ({
          ...current,
          failed: true,
          loadingMore: false,
          version: historyVersion,
        }));
      },
    );
    return () => {
      cancelled = true;
    };
  }, [creditsApi, historyVersion]);

  async function loadMore() {
    const cursor = history.next_cursor;
    if (!cursor || history.loadingMore) return;
    setHistory((current) => ({
      ...current,
      failed: false,
      loadingMore: true,
    }));
    try {
      const page = await creditsApi.getTransactions(cursor);
      if (!mountedRef.current) return;
      setHistory((current) => {
        const knownIds = new Set(current.items.map((item) => item.id));
        return {
          ...current,
          failed: false,
          items: [
            ...current.items,
            ...page.items.filter((item) => !knownIds.has(item.id)),
          ],
          loadingMore: false,
          next_cursor: page.next_cursor,
        };
      });
    } catch {
      if (!mountedRef.current) return;
      setHistory((current) => ({
        ...current,
        failed: true,
        loadingMore: false,
      }));
    }
  }

  if (!balance) {
    return (
      <div className="grid min-h-40 place-items-center px-5 py-8 sm:px-6">
        {balanceFailed ? (
          <div role="alert" className="text-center">
            <p className="text-sm text-[var(--muted)]">
              クレジット情報を読み込めませんでした。
            </p>
            <button
              type="button"
              className="mt-3 h-9 rounded-xl px-3 text-sm font-medium text-[var(--text)] transition-colors hover:bg-[var(--hover)]"
              onClick={() => void refreshBalance()}
            >
              再試行
            </button>
          </div>
        ) : (
          <IOSSpinner label="クレジット情報を読み込み中" />
        )}
      </div>
    );
  }

  const historyLoading = history.version !== historyVersion;

  return (
    <div className="w-full px-5 pb-7 pt-2 sm:px-6 sm:pb-8 sm:pt-2">
      <div className="flex min-h-14 items-center gap-4">
        <span className="min-w-0 flex-1 text-sm font-medium text-[var(--text)]">
          利用可能
        </span>
        <span className="shrink-0 text-sm tabular-nums text-[var(--text)]">
          {formatCreditAmount(balance.available, balance.scale)}
          <span className="ml-1 text-xs text-[var(--muted)]">クレジット</span>
        </span>
      </div>

      {balance.reserved > 0 ? (
        <div className="flex min-h-14 items-center gap-4 border-t border-[var(--separator)]">
          <span className="min-w-0 flex-1 text-sm font-medium text-[var(--text)]">
            予約中
          </span>
          <span className="shrink-0 text-sm tabular-nums text-[var(--muted)]">
            {formatCreditAmount(balance.reserved, balance.scale)}
            <span className="ml-1 text-xs">クレジット</span>
          </span>
        </div>
      ) : null}

      <div className="my-2 h-px bg-[var(--divider)]" />

      <FreeCreditAllowanceMeter
        balance={balance}
        className="py-3"
        variant="settings"
      />

      {balanceFailed ? (
        <div className="flex items-center justify-between gap-3 py-2 text-xs">
          <span role="status" aria-live="polite" className="text-[var(--muted)]">
            最新の残高へ更新できませんでした。
          </span>
          <button
            type="button"
            className="shrink-0 font-medium text-[var(--text)] hover:underline"
            onClick={() => void refreshBalance()}
          >
            再試行
          </button>
        </div>
      ) : null}

      <div className="my-2 h-px bg-[var(--divider)]" />

      <section aria-labelledby="credit-history-title">
        <h2
          id="credit-history-title"
          className="flex min-h-12 items-center text-sm font-medium text-[var(--text)]"
        >
          履歴
        </h2>

        {historyLoading && history.items.length === 0 ? (
          <div className="grid min-h-20 place-items-center">
            <IOSSpinner label="クレジット履歴を読み込み中" />
          </div>
        ) : history.items.length > 0 ? (
          <ul>
            {history.items.map((transaction) => (
              <CreditHistoryItem
                key={transaction.id}
                scale={balance.scale}
                transaction={transaction}
              />
            ))}
          </ul>
        ) : history.failed ? (
          <div className="flex min-h-14 items-center justify-between gap-3 text-sm">
            <span className="text-[var(--muted)]">履歴を読み込めませんでした。</span>
            <button
              type="button"
              className="shrink-0 font-medium text-[var(--text)] hover:underline"
              onClick={() => setHistoryVersion((version) => version + 1)}
            >
              再試行
            </button>
          </div>
        ) : (
          <p className="py-4 text-sm text-[var(--muted)]">履歴はありません。</p>
        )}

        {history.items.length > 0 && history.failed ? (
          <div className="flex min-h-11 items-center justify-between gap-3 text-xs">
            <span role="status" aria-live="polite" className="text-[var(--muted)]">
              続きを読み込めませんでした。
            </span>
            <button
              type="button"
              className="shrink-0 font-medium text-[var(--text)] hover:underline"
              onClick={() => void loadMore()}
            >
              再試行
            </button>
          </div>
        ) : null}

        {history.next_cursor && !history.failed ? (
          <button
            type="button"
            disabled={history.loadingMore}
            className="mt-1 h-10 w-full rounded-xl text-sm font-medium text-[var(--text)] transition-colors hover:bg-[var(--hover)] disabled:text-[var(--muted)]"
            onClick={() => void loadMore()}
          >
            {history.loadingMore ? "読み込み中…" : "さらに表示"}
          </button>
        ) : null}
      </section>
    </div>
  );
}
