"use client";

import { useMemo } from "react";

import { useApiAccessToken } from "@/components/auth/api-access-token-provider";
import { createHumanApi } from "@/lib/human/api";

export function useHumanApi() {
  const accessToken = useApiAccessToken();
  return useMemo(() => createHumanApi(accessToken), [accessToken]);
}
