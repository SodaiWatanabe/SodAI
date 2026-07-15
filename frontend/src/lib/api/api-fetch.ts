"use client";

import type { ApiAccessTokenSource } from "@/lib/auth/api-client";
import { ApiError } from "@/lib/api/api-error";
import { API_BASE_URL } from "@/lib/api/base-url";

export function createApiFetch(accessToken: ApiAccessTokenSource) {
  return async function apiFetch(path: `/${string}`, init: RequestInit = {}) {
    const token = await accessToken.get();
    const headers = new Headers(init.headers);
    if (token) headers.set("Authorization", `Bearer ${token}`);
    if (init.body) headers.set("Content-Type", "application/json");

    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      credentials: "include",
      headers,
    });
    if (response.status === 401 && token) accessToken.invalidate();
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as {
        detail?: string;
      } | null;
      throw new ApiError(
        payload?.detail ?? "SodAI APIへ接続できませんでした。",
        response.status,
      );
    }
    return response;
  };
}
