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
import { listConversations, listModels } from "@/lib/chat/api";
import type { AvailableModel, ConversationSummary } from "@/lib/chat/types";

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

async function loadChatData() {
  const conversations = await listConversations();
  const models = await listModels();
  return { conversations, models };
}

type ChatDataProviderProps = {
  children: ReactNode;
  ownerKey: string;
};

export function ChatDataProvider({ children, ownerKey }: ChatDataProviderProps) {
  const { dismissToast, showToast } = useToast();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [models, setModels] = useState<AvailableModel[]>([]);
  const [loadVersion, setLoadVersion] = useState(0);

  const refresh = useCallback(() => {
    setLoadVersion((version) => version + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void loadChatData().then(
      (data) => {
        if (cancelled) return;
        setConversations(data.conversations);
        setModels(data.models);
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
  }, [dismissToast, loadVersion, ownerKey, refresh, showToast]);

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
