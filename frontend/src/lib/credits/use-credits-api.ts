"use client";

import { useMemo } from "react";

import { useApiAccessToken } from "@/components/auth/api-access-token-provider";
import { createCreditsApi } from "@/lib/credits/api";

export function useCreditsApi() {
  const accessToken = useApiAccessToken();
  return useMemo(() => createCreditsApi(accessToken), [accessToken]);
}
