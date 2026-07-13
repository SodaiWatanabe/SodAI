import "server-only";

import { cache } from "react";

import type { Account } from "@/lib/account/types";
import { API_BASE_URL } from "@/lib/api/base-url";
import { getCurrentApiAccessToken } from "@/lib/auth/session";

const SERVER_API_BASE_URL = (
  process.env.SODAI_API_BASE_URL ?? API_BASE_URL
).replace(/\/$/, "");

export const getCurrentAccount = cache(async (): Promise<Account | null> => {
  try {
    const token = await getCurrentApiAccessToken();
    if (!token) return null;

    const response = await fetch(`${SERVER_API_BASE_URL}/api/v1/account/me`, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(3_000),
    });
    if (!response.ok) return null;
    return (await response.json()) as Account;
  } catch {
    return null;
  }
});
