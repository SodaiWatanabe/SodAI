"use client";

import type { Account } from "@/lib/account/types";
import { API_BASE_URL } from "@/lib/api/base-url";
import { getApiAccessToken } from "@/lib/auth/api-client";

export class AccountApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AccountApiError";
  }
}

async function accountRequest(
  path: "/api/v1/account/me",
  init: RequestInit = {},
): Promise<Account> {
  const token = await getApiAccessToken();
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body) headers.set("Content-Type", "application/json");

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    throw new AccountApiError("アカウント情報を確認できませんでした。");
  }
  return (await response.json()) as Account;
}

export function getCurrentAccount(): Promise<Account> {
  return accountRequest("/api/v1/account/me");
}

export function setCurrentAccountDisplayName(
  displayName: string,
): Promise<Account> {
  return accountRequest("/api/v1/account/me", {
    method: "PATCH",
    body: JSON.stringify({ display_name: displayName }),
  });
}
