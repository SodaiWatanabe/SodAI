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

import { useChatRealtime } from "@/components/chat/use-chat-realtime";
import { useToast } from "@/components/ui/toast-provider";
import type {
  AvailableAnswerer,
  RealtimeEvent,
  ThreadSummary,
} from "@/lib/chat/types";
import { useChatApi } from "@/lib/chat/use-chat-api";

type ThreadPatch = Partial<
  Pick<
    ThreadSummary,
    "answerer" | "last_activity_at" | "revision" | "title" | "updated_at"
  >
>;

type ChatDataContextValue = {
  answerers: AvailableAnswerer[];
  archiveThread: (id: string) => Promise<void>;
  patchThread: (id: string, patch: ThreadPatch) => void;
  realtimeReadyRevision: number;
  refresh: () => void;
  renameThread: (id: string, title: string) => Promise<ThreadSummary>;
  subscribeRealtime: (listener: RealtimeListener) => () => void;
  threads: ThreadSummary[];
  upsertThread: (thread: ThreadSummary) => void;
};

type RealtimeListener = (event: RealtimeEvent) => void;

const ChatDataContext = createContext<ChatDataContextValue | null>(null);

function byLatestActivity(left: ThreadSummary, right: ThreadSummary) {
  return Date.parse(right.last_activity_at) - Date.parse(left.last_activity_at);
}

export function ChatDataProvider({ children }: { children: ReactNode }) {
  const chatApi = useChatApi();
  const { dismissToast, showToast } = useToast();
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [answerers, setAnswerers] = useState<AvailableAnswerer[]>([]);
  const [loadVersion, setLoadVersion] = useState(0);
  const [realtimeReadyRevision, setRealtimeReadyRevision] = useState(0);
  const realtimeListenersRef = useRef(new Set<RealtimeListener>());
  const threadMutationVersionRef = useRef(0);

  const refresh = useCallback(() => {
    setLoadVersion((version) => version + 1);
  }, []);

  const patchThread = useCallback((id: string, patch: ThreadPatch) => {
    threadMutationVersionRef.current += 1;
    setThreads((current) => {
      const next = current.map((thread) => {
        if (thread.id !== id) return thread;
        if (patch.revision !== undefined && patch.revision < thread.revision) {
          return thread;
        }
        return { ...thread, ...patch };
      });
      return patch.last_activity_at ? next.sort(byLatestActivity) : next;
    });
  }, []);

  const removeThread = useCallback((id: string) => {
    threadMutationVersionRef.current += 1;
    setThreads((current) => current.filter((thread) => thread.id !== id));
  }, []);

  const upsertThread = useCallback((thread: ThreadSummary) => {
    threadMutationVersionRef.current += 1;
    setThreads((current) => {
      const existing = current.find((item) => item.id === thread.id);
      const freshest =
        existing && existing.revision > thread.revision ? existing : thread;
      return [freshest, ...current.filter((item) => item.id !== thread.id)].sort(
        byLatestActivity,
      );
    });
  }, []);

  const subscribeRealtime = useCallback((listener: RealtimeListener) => {
    realtimeListenersRef.current.add(listener);
    return () => realtimeListenersRef.current.delete(listener);
  }, []);

  const handleRealtime = useCallback(
    (event: RealtimeEvent) => {
      if (
        event.type === "thread.created" &&
        event.data.title &&
        event.data.answerer &&
        event.data.created_at &&
        event.data.updated_at &&
        event.data.last_activity_at
      ) {
        upsertThread({
          id: event.thread_id,
          space_id: event.space_id,
          title: event.data.title,
          answerer: event.data.answerer,
          revision: event.thread_revision,
          created_at: event.data.created_at,
          updated_at: event.data.updated_at,
          last_activity_at: event.data.last_activity_at,
        });
      } else if (event.type === "thread.updated" && event.data.title) {
        patchThread(event.thread_id, {
          title: event.data.title,
          revision: event.thread_revision,
          updated_at: event.data.updated_at,
        });
      } else if (event.type === "thread.archived") {
        removeThread(event.thread_id);
      } else if (event.type === "entry.created") {
        patchThread(event.thread_id, {
          answerer: event.data.answerer,
          last_activity_at: event.data.last_activity_at ?? event.occurred_at,
          revision: event.thread_revision,
        });
      } else if (
        event.type === "response.completed" ||
        event.type === "response.failed"
      ) {
        patchThread(event.thread_id, {
          last_activity_at: event.occurred_at,
          revision: event.thread_revision,
        });
      } else if (event.type === "sync.required") {
        refresh();
      }

      for (const listener of realtimeListenersRef.current) listener(event);
    },
    [patchThread, refresh, removeThread, upsertThread],
  );

  const handleRealtimeReady = useCallback(() => {
    setRealtimeReadyRevision((revision) => revision + 1);
  }, []);

  useChatRealtime(
    chatApi.createRealtimeSocket,
    handleRealtime,
    handleRealtimeReady,
  );

  useEffect(() => {
    let cancelled = false;
    const mutationVersion = threadMutationVersionRef.current;
    void Promise.all([chatApi.listThreads(), chatApi.listAnswerers()]).then(
      ([loadedThreads, loadedAnswerers]) => {
        if (cancelled) return;
        if (mutationVersion !== threadMutationVersionRef.current) {
          refresh();
          return;
        }
        setThreads(loadedThreads);
        setAnswerers(loadedAnswerers);
        dismissToast("thread-list-load");
      },
      () => {
        if (cancelled) return;
        showToast({
          id: "thread-list-load",
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
  }, [
    chatApi,
    dismissToast,
    loadVersion,
    realtimeReadyRevision,
    refresh,
    showToast,
  ]);

  const value = useMemo<ChatDataContextValue>(
    () => ({
      answerers,
      archiveThread: async (id) => {
        await chatApi.archiveThread(id);
        removeThread(id);
      },
      patchThread,
      realtimeReadyRevision,
      refresh,
      renameThread: async (id, title) => {
        const thread = await chatApi.updateThread(id, title);
        patchThread(id, thread);
        return thread;
      },
      subscribeRealtime,
      threads,
      upsertThread,
    }),
    [
      answerers,
      chatApi,
      patchThread,
      realtimeReadyRevision,
      refresh,
      removeThread,
      subscribeRealtime,
      threads,
      upsertThread,
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
