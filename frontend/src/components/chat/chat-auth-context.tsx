"use client";

import {
  createContext,
  type ReactNode,
  useContext,
  useMemo,
} from "react";

type ChatAuthContextValue = {
  authenticated: boolean;
  openAuth: () => void;
  settingsAccessible: boolean;
};

const ChatAuthContext = createContext<ChatAuthContextValue | null>(null);

type ChatAuthProviderProps = ChatAuthContextValue & {
  children: ReactNode;
};

export function ChatAuthProvider({
  authenticated,
  children,
  openAuth,
  settingsAccessible,
}: ChatAuthProviderProps) {
  const value = useMemo(
    () => ({ authenticated, openAuth, settingsAccessible }),
    [authenticated, openAuth, settingsAccessible],
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
