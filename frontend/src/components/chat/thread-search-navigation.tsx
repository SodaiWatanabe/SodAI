"use client";

import { createContext, type ReactNode, useContext } from "react";

export type ThreadSearchNavigationTarget = {
  entryId: string;
  query: string;
  sequence: number;
  threadId: string;
};

const ThreadSearchNavigationContext =
  createContext<ThreadSearchNavigationTarget | null>(null);

export function ThreadSearchNavigationProvider({
  children,
  target,
}: {
  children: ReactNode;
  target: ThreadSearchNavigationTarget | null;
}) {
  return (
    <ThreadSearchNavigationContext.Provider value={target}>
      {children}
    </ThreadSearchNavigationContext.Provider>
  );
}

export function useThreadSearchNavigationTarget() {
  return useContext(ThreadSearchNavigationContext);
}
