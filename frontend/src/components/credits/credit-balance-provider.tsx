"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import type { CreditBalance } from "@/lib/credits/types";
import { useCreditsApi } from "@/lib/credits/use-credits-api";

type CreditBalanceContextValue = {
  balance?: CreditBalance;
  failed: boolean;
  loading: boolean;
  refreshBalance: () => Promise<void>;
};

const CreditBalanceContext = createContext<CreditBalanceContextValue | null>(
  null,
);

export function CreditBalanceProvider({ children }: { children: ReactNode }) {
  const creditsApi = useCreditsApi();
  const mountedRef = useRef(true);
  const requestRef = useRef<Promise<void> | undefined>(undefined);
  const [state, setState] = useState<
    Pick<CreditBalanceContextValue, "balance" | "failed" | "loading">
  >({ failed: false, loading: false });

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const refreshBalance = useCallback(() => {
    if (requestRef.current) return requestRef.current;

    setState((current) => ({ ...current, failed: false, loading: true }));
    const request = creditsApi.getBalance().then(
      (balance) => {
        if (!mountedRef.current) return;
        setState({ balance, failed: false, loading: false });
      },
      () => {
        if (!mountedRef.current) return;
        setState((current) => ({ ...current, failed: true, loading: false }));
      },
    );
    requestRef.current = request;
    void request.finally(() => {
      if (requestRef.current === request) requestRef.current = undefined;
    });
    return request;
  }, [creditsApi]);
  const value = useMemo(
    () => ({ ...state, refreshBalance }),
    [refreshBalance, state],
  );

  return (
    <CreditBalanceContext.Provider value={value}>
      {children}
    </CreditBalanceContext.Provider>
  );
}

export function useCreditBalance() {
  const context = useContext(CreditBalanceContext);
  if (!context) {
    throw new Error("useCreditBalance must be used inside CreditBalanceProvider");
  }
  return context;
}
