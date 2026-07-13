"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";

import {
  createMessageSendCookie,
  type MessageSendPreference,
} from "@/lib/preferences/message-send";

type MessageSendPreferenceContextValue = {
  preference: MessageSendPreference;
  setPreference: (preference: MessageSendPreference) => void;
};

type MessageSendPreferenceProviderProps = {
  children: ReactNode;
  initialPreference: MessageSendPreference;
};

const MessageSendPreferenceContext =
  createContext<MessageSendPreferenceContextValue | null>(null);

export function MessageSendPreferenceProvider({
  children,
  initialPreference,
}: MessageSendPreferenceProviderProps) {
  const [preference, setPreferenceState] =
    useState<MessageSendPreference>(initialPreference);

  const setPreference = useCallback(
    (nextPreference: MessageSendPreference) => {
      setPreferenceState(nextPreference);
      document.cookie = createMessageSendCookie(
        nextPreference,
        window.location.protocol === "https:",
      );
    },
    [],
  );

  const context = useMemo(
    () => ({ preference, setPreference }),
    [preference, setPreference],
  );

  return (
    <MessageSendPreferenceContext.Provider value={context}>
      {children}
    </MessageSendPreferenceContext.Provider>
  );
}

export function useMessageSendPreference() {
  const context = useContext(MessageSendPreferenceContext);

  if (!context) {
    throw new Error(
      "useMessageSendPreference must be used inside MessageSendPreferenceProvider.",
    );
  }

  return context;
}
