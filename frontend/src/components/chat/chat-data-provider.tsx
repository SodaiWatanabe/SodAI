"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { useToast } from "@/components/ui/toast-provider";
import type { AvailableModel, ConversationSummary } from "@/lib/chat/types";
import { useChatApi } from "@/lib/chat/use-chat-api";

type ConversationPatch = Partial<
  Pick<ConversationSummary, "last_activity_at" | "model" | "title">
>;

type ChatDataContextValue = {
  conversations: ConversationSummary[];
  models: AvailableModel[];
  patchConversation: (id: string, patch: ConversationPatch) => void;
  refresh: () => void;
  upsertConversation: (conversation: ConversationSummary) => void;
};

const ChatDataContext = createContext<ChatDataContextValue | null>(null);

export function ChatDataProvider({ children }: { children: ReactNode }) {
  const chatApi = useChatApi();
  const { dismissToast, showToast } = useToast();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [models, setModels] = useState<AvailableModel[]>([]);
  const [loadVersion, setLoadVersion] = useState(0);

  const refresh = useCallback(() => {
    setLoadVersion((version) => version + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([chatApi.listConversations(), chatApi.listModels()]).then(
      ([conversations, models]) => {
        if (cancelled) return;
        setConversations(conversations);
        setModels(models);
        dismissToast("conversation-list-load");
      },
      () => {
        if (cancelled) return;
        showToast({
          id: "conversation-list-load",
          message: "会話一覧を読み込めませんでした。",
          tone: "error",
          duration: null,
          action: { label: "再試行", onClick: refresh },
        });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [chatApi, dismissToast, loadVersion, refresh, showToast]);

  const value = useMemo<ChatDataContextValue>(
    () => ({
      conversations,
      models,
      patchConversation: (id, patch) => {
        setConversations((current) =>
          current.map((conversation) =>
            conversation.id === id ? { ...conversation, ...patch } : conversation,
          ),
        );
      },
      refresh,
      upsertConversation: (conversation) => {
        setConversations((current) => [
          conversation,
          ...current.filter((item) => item.id !== conversation.id),
        ]);
      },
    }),
    [conversations, models, refresh],
  );

  return <ChatDataContext.Provider value={value}>{children}</ChatDataContext.Provider>;
}

export function useChatData() {
  const context = useContext(ChatDataContext);
  if (!context) {
    throw new Error("useChatData must be used inside ChatDataProvider");
  }
  return context;
}
