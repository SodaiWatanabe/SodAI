"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useRef,
} from "react";

import {
  type ApiAccessTokenSource,
  getApiAccessToken,
} from "@/lib/auth/api-client";

type CachedToken = {
  expiresAt: number;
  value: string;
};

const EXPIRY_SKEW_MS = 30_000;
const ApiAccessTokenContext = createContext<ApiAccessTokenSource | null>(null);

function readTokenExpiry(token: string): number {
  try {
    const payload = token.split(".").at(1);
    if (!payload) return 0;
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=");
    const decoded = JSON.parse(atob(padded)) as { exp?: unknown };
    return typeof decoded.exp === "number" ? decoded.exp * 1000 : 0;
  } catch {
    return 0;
  }
}

type ApiAccessTokenProviderProps = {
  authenticated: boolean;
  children: ReactNode;
};

export function ApiAccessTokenProvider({
  authenticated,
  children,
}: ApiAccessTokenProviderProps) {
  const cacheRef = useRef<CachedToken | undefined>(undefined);
  const generationRef = useRef(0);
  const requestRef = useRef<Promise<string> | undefined>(undefined);

  const invalidate = useCallback(() => {
    generationRef.current += 1;
    cacheRef.current = undefined;
    requestRef.current = undefined;
  }, []);

  const get = useCallback(async () => {
    if (!authenticated) return null;

    const now = Date.now();
    const cached = cacheRef.current;
    if (cached && cached.expiresAt - EXPIRY_SKEW_MS > now) {
      return cached.value;
    }
    if (requestRef.current) return requestRef.current;

    const generation = generationRef.current;
    const request = getApiAccessToken().then((token) => {
      const expiresAt = readTokenExpiry(token);
      if (generation === generationRef.current && expiresAt > Date.now()) {
        cacheRef.current = { expiresAt, value: token };
      }
      return token;
    });
    requestRef.current = request;

    try {
      return await request;
    } finally {
      if (requestRef.current === request) requestRef.current = undefined;
    }
  }, [authenticated]);

  const value = useMemo<ApiAccessTokenSource>(
    () => ({ get, invalidate }),
    [get, invalidate],
  );

  return (
    <ApiAccessTokenContext.Provider value={value}>
      {children}
    </ApiAccessTokenContext.Provider>
  );
}

export function useApiAccessToken() {
  const context = useContext(ApiAccessTokenContext);
  if (!context) {
    throw new Error("useApiAccessToken must be used inside ApiAccessTokenProvider");
  }
  return context;
}
