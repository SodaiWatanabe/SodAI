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

import { useToast } from "@/components/ui/toast-provider";
import { useChatRealtime } from "@/components/chat/use-chat-realtime";
import type {
  AvailableModel,
  ConversationSummary,
  RealtimeEvent,
} from "@/lib/chat/types";
import { useChatApi } from "@/lib/chat/use-chat-api";

type ConversationPatch = Partial<
  Pick<
    ConversationSummary,
    "last_activity_at" | "model" | "title" | "updated_at"
  >
>;

type ChatDataContextValue = {
  archiveConversation: (id: string) => Promise<void>;
  conversations: ConversationSummary[];
  models: AvailableModel[];
  patchConversation: (id: string, patch: ConversationPatch) => void;
  renameConversation: (id: string, title: string) => Promise<ConversationSummary>;
  refresh: () => void;
  subscribeRealtime: (listener: RealtimeListener) => () => void;
  upsertConversation: (conversation: ConversationSummary) => void;
};

type RealtimeListener = (event: RealtimeEvent) => void;

const ChatDataContext = createContext<ChatDataContextValue | null>(null);

function byLatestActivity(
  left: ConversationSummary,
  right: ConversationSummary,
) {
  return Date.parse(right.last_activity_at) - Date.parse(left.last_activity_at);
}

export function ChatDataProvider({ children }: { children: ReactNode }) {
  const chatApi = useChatApi();
  const { dismissToast, showToast } = useToast();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [models, setModels] = useState<AvailableModel[]>([]);
  const [loadVersion, setLoadVersion] = useState(0);
  const realtimeListenersRef = useRef(new Set<RealtimeListener>());

  const refresh = useCallback(() => {
    setLoadVersion((version) => version + 1);
  }, []);

  const patchConversation = useCallback(
    (id: string, patch: ConversationPatch) => {
      setConversations((current) => {
        const next = current.map((conversation) =>
          conversation.id === id ? { ...conversation, ...patch } : conversation,
        );
        return patch.last_activity_at ? next.sort(byLatestActivity) : next;
      });
    },
    [],
  );

  const removeConversation = useCallback((id: string) => {
    setConversations((current) =>
      current.filter((conversation) => conversation.id !== id),
    );
  }, []);

  const upsertConversation = useCallback((conversation: ConversationSummary) => {
    setConversations((current) =>
      [conversation, ...current.filter((item) => item.id !== conversation.id)].sort(
        byLatestActivity,
      ),
    );
  }, []);

  const subscribeRealtime = useCallback((listener: RealtimeListener) => {
    realtimeListenersRef.current.add(listener);
    return () => realtimeListenersRef.current.delete(listener);
  }, []);

  const handleRealtime = useCallback(
    (event: RealtimeEvent) => {
      if (
        event.type === "conversation.created" &&
        event.data.title &&
        event.data.model &&
        event.data.created_at &&
        event.data.updated_at &&
        event.data.last_activity_at
      ) {
        upsertConversation({
          id: event.conversation_id,
          title: event.data.title,
          model: event.data.model,
          created_at: event.data.created_at,
          updated_at: event.data.updated_at,
          last_activity_at: event.data.last_activity_at,
        });
      } else if (event.type === "conversation.updated" && event.data.title) {
        patchConversation(event.conversation_id, {
          title: event.data.title,
          updated_at: event.data.updated_at,
        });
      } else if (event.type === "conversation.archived") {
        removeConversation(event.conversation_id);
      } else if (event.type === "message.created") {
        const patch: ConversationPatch = {
          last_activity_at: event.data.last_activity_at ?? event.occurred_at,
        };
        if (event.data.model) patch.model = event.data.model;
        patchConversation(event.conversation_id, patch);
      } else if (
        event.type === "response.completed" ||
        event.type === "response.failed"
      ) {
        patchConversation(event.conversation_id, {
          last_activity_at: event.occurred_at,
        });
      }

      for (const listener of realtimeListenersRef.current) listener(event);
    },
    [patchConversation, removeConversation, upsertConversation],
  );

  useChatRealtime(chatApi.createRealtimeSocket, handleRealtime);

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
      archiveConversation: async (id) => {
        await chatApi.archiveConversation(id);
        removeConversation(id);
      },
      conversations,
      models,
      patchConversation,
      renameConversation: async (id, title) => {
        const conversation = await chatApi.updateConversation(id, title);
        patchConversation(id, conversation);
        return conversation;
      },
      refresh,
      subscribeRealtime,
      upsertConversation,
    }),
    [
      chatApi,
      conversations,
      models,
      patchConversation,
      refresh,
      removeConversation,
      subscribeRealtime,
      upsertConversation,
    ],
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
