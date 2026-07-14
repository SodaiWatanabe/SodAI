export type FreeCreditAllowance = {
  limit: number;
  used: number;
  reserved: number;
  remaining: number;
  starts_at: string;
  expires_at: string;
};

export type CreditBalance = {
  asset_code: string;
  scale: number;
  available: number;
  reserved: number;
  free_allowance: FreeCreditAllowance | null;
};

export type CreditSourceKind =
  | "admin"
  | "earned"
  | "promotional"
  | "purchased"
  | "subscription";

export type CreditTransactionKind =
  | "expire"
  | "grant"
  | "release"
  | "reserve"
  | "settle";

export type CreditTransaction = {
  id: string;
  kind: CreditTransactionKind;
  available_delta: number;
  reserved_delta: number;
  source_kind: CreditSourceKind | null;
  expires_at: string | null;
  created_at: string;
};

export type CreditTransactionPage = {
  items: CreditTransaction[];
  next_cursor: string | null;
};
