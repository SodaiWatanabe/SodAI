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
