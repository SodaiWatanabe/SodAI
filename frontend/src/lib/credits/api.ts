"use client";

import { API_BASE_URL } from "@/lib/api/base-url";
import type { ApiAccessTokenSource } from "@/lib/auth/api-client";
import type {
  CreditBalance,
  CreditTransactionPage,
} from "@/lib/credits/types";

export function createCreditsApi(accessToken: ApiAccessTokenSource) {
  async function get(path: string) {
    const token = await accessToken.get();
    const headers = new Headers();
    if (token) headers.set("Authorization", `Bearer ${token}`);

    const response = await fetch(`${API_BASE_URL}${path}`, {
      cache: "no-store",
      credentials: "include",
      headers,
    });
    if (response.status === 401 && token) accessToken.invalidate();
    if (!response.ok) {
      throw new Error("クレジット利用状況を取得できませんでした。");
    }
    return response;
  }

  async function getBalance(): Promise<CreditBalance> {
    const response = await get("/api/v1/credits");
    return (await response.json()) as CreditBalance;
  }

  async function getTransactions(
    cursor?: string,
    limit = 20,
  ): Promise<CreditTransactionPage> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (cursor) params.set("cursor", cursor);
    const response = await get(
      `/api/v1/credits/transactions?${params.toString()}`,
    );
    return (await response.json()) as CreditTransactionPage;
  }

  return { getBalance, getTransactions };
}

export type CreditsApi = ReturnType<typeof createCreditsApi>;
