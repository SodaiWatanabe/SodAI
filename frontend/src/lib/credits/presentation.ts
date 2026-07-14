import type {
  CreditSourceKind,
  CreditTransaction,
  FreeCreditAllowance,
} from "./types.ts";

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

export type FreeCreditAllowancePresentation = {
  remainingPercent: number;
  resetAt: string | Date;
};

export function presentFreeCreditAllowance(
  allowance: FreeCreditAllowance | null,
  now: Date,
): FreeCreditAllowancePresentation {
  if (!allowance) {
    return {
      remainingPercent: 100,
      resetAt: projectFreeAllowanceExpiry(now),
    };
  }
  return {
    remainingPercent: Math.round(
      creditAllowanceRemainingRatio(allowance) * 100,
    ),
    resetAt: allowance.expires_at,
  };
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

export function formatCreditAmount(
  amount: number,
  scale: number,
  showPositiveSign = false,
): string {
  if (scale <= 0) return "0";
  return new Intl.NumberFormat("ja-JP", {
    maximumFractionDigits: 6,
    signDisplay: showPositiveSign ? "exceptZero" : "auto",
  }).format(amount / scale);
}

export function formatCreditTransactionDate(createdAt: string): string {
  return new Intl.DateTimeFormat("ja-JP", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(createdAt));
}

function grantLabel(sourceKind: CreditSourceKind | null) {
  switch (sourceKind) {
    case "earned":
      return "獲得クレジット";
    case "promotional":
      return "プロモーションクレジット";
    case "purchased":
      return "購入クレジット";
    case "subscription":
      return "サブスクリプションクレジット";
    default:
      return "クレジット付与";
  }
}

export type CreditTransactionPresentation = {
  amount: number;
  label: string;
  tone: "decrease" | "increase" | "neutral";
};

export function presentCreditTransaction(
  transaction: CreditTransaction,
): CreditTransactionPresentation {
  switch (transaction.kind) {
    case "grant":
      return {
        amount: transaction.available_delta,
        label: grantLabel(transaction.source_kind),
        tone: "increase",
      };
    case "reserve":
      return {
        amount: Math.abs(transaction.reserved_delta),
        label: "クレジットを予約",
        tone: "neutral",
      };
    case "settle":
      return {
        amount: transaction.available_delta + transaction.reserved_delta,
        label: "モデルの利用",
        tone: "decrease",
      };
    case "release":
      return {
        amount: Math.abs(transaction.reserved_delta),
        label: "予約を解除",
        tone: "neutral",
      };
    case "expire":
      return {
        amount: transaction.available_delta,
        label: "有効期限切れ",
        tone: "decrease",
      };
  }
}
