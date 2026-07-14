"use client";

import { API_BASE_URL } from "@/lib/api/base-url";
import type { ApiAccessTokenSource } from "@/lib/auth/api-client";
import type { CreditBalance } from "@/lib/credits/types";

export function createCreditsApi(accessToken: ApiAccessTokenSource) {
  async function getBalance(): Promise<CreditBalance> {
    const token = await accessToken.get();
    const headers = new Headers();
    if (token) headers.set("Authorization", `Bearer ${token}`);

    const response = await fetch(`${API_BASE_URL}/api/v1/credits`, {
      cache: "no-store",
      credentials: "include",
      headers,
    });
    if (response.status === 401 && token) accessToken.invalidate();
    if (!response.ok) {
      throw new Error("クレジット利用状況を取得できませんでした。");
    }
    return (await response.json()) as CreditBalance;
  }

  return { getBalance };
}

export type CreditsApi = ReturnType<typeof createCreditsApi>;
