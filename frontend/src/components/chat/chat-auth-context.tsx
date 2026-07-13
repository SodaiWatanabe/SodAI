"use client";

import {
  createContext,
  type ReactNode,
  useContext,
  useMemo,
} from "react";

import type { AuthMode } from "@/components/auth/auth-dialog";

type ChatAuthContextValue = {
  authenticated: boolean;
  openAuth: (mode: AuthMode) => void;
};

const ChatAuthContext = createContext<ChatAuthContextValue | null>(null);

type ChatAuthProviderProps = ChatAuthContextValue & {
  children: ReactNode;
};

export function ChatAuthProvider({
  authenticated,
  children,
  openAuth,
}: ChatAuthProviderProps) {
  const value = useMemo(
    () => ({ authenticated, openAuth }),
    [authenticated, openAuth],
  );

  return (
    <ChatAuthContext.Provider value={value}>
      {children}
    </ChatAuthContext.Provider>
  );
}

export function useChatAuth() {
  const context = useContext(ChatAuthContext);
  if (!context) {
    throw new Error("useChatAuth must be used inside ChatAuthProvider");
  }
  return context;
}
