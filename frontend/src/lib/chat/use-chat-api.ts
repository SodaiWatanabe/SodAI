"use client";

import { useMemo } from "react";

import { useApiAccessToken } from "@/components/auth/api-access-token-provider";
import { createChatApi } from "@/lib/chat/api";

export function useChatApi() {
  const accessToken = useApiAccessToken();
  return useMemo(() => createChatApi(accessToken), [accessToken]);
}
