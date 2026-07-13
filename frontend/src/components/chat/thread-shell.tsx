"use client";

import { ArrowDown, ArrowUp } from "lucide-react";
import {
  type FormEvent,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

import { useChatData } from "@/components/chat/chat-data-provider";
import { ChatHeader } from "@/components/chat/chat-header";
import { settleComposerFocus } from "@/components/chat/composer-focus";
import { reduceThreadRealtime } from "@/components/chat/thread-realtime";
import { ThreadViewport } from "@/components/chat/thread-viewport";
import { useToast } from "@/components/ui/toast-provider";
import type {
  AvailableAnswerer,
  RealtimeEvent,
  Thread,
  ThreadEntry,
} from "@/lib/chat/types";
import { useChatApi } from "@/lib/chat/use-chat-api";

type ThreadShellProps = {
  threadId: string;
};

const STICK_TO_BOTTOM_THRESHOLD = 120;

function mergeEntries(current: ThreadEntry[], incoming: ThreadEntry[]) {
  const byId = new Map(current.map((entry) => [entry.id, entry]));
  for (const entry of incoming) byId.set(entry.id, entry);
  return [...byId.values()].sort((left, right) => left.ordinal - right.ordinal);
}

function isResponding(thread?: Thread) {
  const status = thread?.latest_response?.status;
  return status === "queued" || status === "running";
}

export function ThreadShell({ threadId }: ThreadShellProps) {
  const { createResponse, getThread } = useChatApi();
  const {
    answerers,
    patchThread,
    realtimeReadyRevision,
    subscribeRealtime,
  } = useChatData();
  const { dismissToast, showToast } = useToast();
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const threadRef = useRef<Thread | undefined>(undefined);
  const initialScrollPositionedRef = useRef(false);
  const answererInitializedRef = useRef(false);
  const stickToBottomRef = useRef(true);
  const mountedRef = useRef(true);
  const refreshGenerationRef = useRef(0);
  const pendingExecutionSyncRef = useRef<string | undefined>(undefined);
  const executionSyncDirtyRef = useRef(false);
  const [thread, setThreadState] = useState<Thread>();
  const [answerer, setAnswerer] = useState<AvailableAnswerer["id"]>();
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const responding = submitting || isResponding(thread);

  const updateThread = useCallback(
    (update: (current?: Thread) => Thread | undefined) => {
      const next = update(threadRef.current);
      threadRef.current = next;
      setThreadState(next);
    },
    [],
  );

  const loadThread = useCallback(() => getThread(threadId), [getThread, threadId]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      dismissToast("message-send");
    };
  }, [dismissToast]);

  useEffect(() => {
    let cancelled = false;

    async function syncThread(showLoading: boolean) {
      if (cancelled) return;
      const generation = ++refreshGenerationRef.current;
      if (showLoading) setLoading(true);
      try {
        const current = await loadThread();
        if (cancelled || generation !== refreshGenerationRef.current) return;
        updateThread((previous) =>
          previous?.id === current.id && previous.revision > current.revision
            ? previous
            : {
                ...current,
                entries:
                  previous?.id === current.id
                    ? mergeEntries(previous.entries, current.entries)
                    : current.entries,
              },
        );
        if (!answererInitializedRef.current) {
          answererInitializedRef.current = true;
          setAnswerer(current.answerer);
        }
        dismissToast("thread-load");
      } catch {
        if (cancelled || generation !== refreshGenerationRef.current) return;
        showToast({
          id: "thread-load",
          message: "会話を読み込めませんでした。",
          tone: "error",
          duration: null,
          action: {
            label: "再試行",
            onClick: () => void syncThread(true),
          },
        });
      } finally {
        if (!cancelled && generation === refreshGenerationRef.current) {
          setLoading(false);
        }
      }
    }

    function syncExecutionOnce(executionId: string | null) {
      const key = executionId ?? "thread";
      if (pendingExecutionSyncRef.current === key) {
        executionSyncDirtyRef.current = true;
        return;
      }
      pendingExecutionSyncRef.current = key;
      void syncThread(false).finally(() => {
        if (pendingExecutionSyncRef.current === key) {
          pendingExecutionSyncRef.current = undefined;
          if (executionSyncDirtyRef.current) {
            executionSyncDirtyRef.current = false;
            syncExecutionOnce(executionId);
          }
        }
      });
    }

    function applyRealtime(event: RealtimeEvent) {
      if (event.type === "sync.required") {
        void syncThread(false);
        return;
      }
      if (event.thread_id !== threadId) return;
      if (event.type === "entry.created") {
        void syncThread(false);
        return;
      }
      if (event.type === "thread.updated" && event.data.title) {
        updateThread((current) =>
          current && event.thread_revision >= current.revision
            ? {
                ...current,
                title: event.data.title ?? current.title,
                revision: event.thread_revision,
              }
            : current,
        );
        return;
      }
      const decision = reduceThreadRealtime(threadRef.current, event);
      if (!decision.handled) return;
      if (decision.next !== threadRef.current) {
        updateThread(() => decision.next);
      }
      if (decision.shouldSync) syncExecutionOnce(event.execution_id);
    }

    const unsubscribeRealtime = subscribeRealtime(applyRealtime);
    void syncThread(false);
    return () => {
      cancelled = true;
      refreshGenerationRef.current += 1;
      pendingExecutionSyncRef.current = undefined;
      executionSyncDirtyRef.current = false;
      unsubscribeRealtime();
      dismissToast("thread-load");
    };
  }, [
    dismissToast,
    loadThread,
    realtimeReadyRevision,
    showToast,
    subscribeRealtime,
    threadId,
    updateThread,
  ]);

  useLayoutEffect(() => {
    const element = scrollRef.current;
    if (!element || !thread) return;
    if (!initialScrollPositionedRef.current) {
      element.scrollTop = element.scrollHeight;
      initialScrollPositionedRef.current = true;
      stickToBottomRef.current = true;
      setShowScrollToBottom(false);
      return;
    }
    if (stickToBottomRef.current) {
      element.scrollTo({ top: element.scrollHeight, behavior: "smooth" });
    }
  }, [thread]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const input = message.trim();
    if (!input || !answerer || responding) return;
    stickToBottomRef.current = true;
    setShowScrollToBottom(false);
    setMessage("");
    setSubmitting(true);
    settleComposerFocus(inputRef.current);
    dismissToast("message-send");
    try {
      const created = await createResponse(threadId, input, answerer);
      if (!mountedRef.current) return;
      updateThread((current) => {
        const entries = current
          ? mergeEntries(current.entries, created.thread.entries)
          : created.thread.entries;
        if (current && current.revision > created.thread.revision) {
          return {
            ...current,
            entries,
            latest_response:
              current.latest_response?.id === created.response.id
                ? current.latest_response
                : created.response,
          };
        }
        return { ...created.thread, entries, latest_response: created.response };
      });
      setSubmitting(false);
      patchThread(threadId, {
        answerer,
        last_activity_at: created.thread.last_activity_at,
        revision: created.thread.revision,
      });
    } catch {
      if (!mountedRef.current) return;
      setMessage((current) => (current.trim() ? current : input));
      setSubmitting(false);
      showToast({
        id: "message-send",
        message: "送信できませんでした。もう一度お試しください。",
        tone: "error",
      });
    }
  }

  function scrollToBottom() {
    const element = scrollRef.current;
    if (!element) return;
    stickToBottomRef.current = true;
    setShowScrollToBottom(false);
    element.scrollTo({ top: element.scrollHeight, behavior: "smooth" });
  }

  return (
    <div
      ref={scrollRef}
      className="flex min-h-0 flex-1 flex-col overflow-y-auto scroll-smooth"
      onScroll={(event) => {
        const element = event.currentTarget;
        const distanceFromBottom =
          element.scrollHeight - element.scrollTop - element.clientHeight;
        const nearBottom = distanceFromBottom <= STICK_TO_BOTTOM_THRESHOLD;
        stickToBottomRef.current = nearBottom;
        setShowScrollToBottom(!nearBottom);
      }}
    >
      <ChatHeader
        answerer={answerer}
        answerers={answerers}
        onAnswererChange={setAnswerer}
      />

      <ThreadViewport thread={thread} loading={loading} responding={responding} />

      <div className="thread-composer sticky bottom-0 z-20 shrink-0 px-5 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-8">
        <button
          type="button"
          aria-label="会話の最下部へ移動"
          aria-hidden={!showScrollToBottom}
          tabIndex={showScrollToBottom ? 0 : -1}
          className={`absolute -top-12 left-1/2 z-20 grid size-9 -translate-x-1/2 place-items-center rounded-full border border-[var(--divider)] bg-[var(--surface-translucent)] text-[var(--muted)] shadow-[0_8px_24px_var(--popover-shadow)] backdrop-blur-xl transition-[opacity,translate,background-color,color] hover:bg-[var(--hover)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] ${
            showScrollToBottom
              ? "translate-y-0 opacity-100"
              : "pointer-events-none translate-y-1 opacity-0"
          }`}
          onClick={scrollToBottom}
        >
          <ArrowDown aria-hidden="true" className="size-4" strokeWidth={2} />
        </button>
        <form onSubmit={submit} className="relative z-10 mx-auto max-w-[760px]">
          <label htmlFor="thread-message" className="sr-only">
            対話を続ける
          </label>
          <input
            ref={inputRef}
            id="thread-message"
            type="text"
            value={message}
            autoFocus
            placeholder="対話を続ける"
            autoComplete="off"
            spellCheck="true"
            onChange={(event) => setMessage(event.target.value)}
            className="chat-input block h-14 w-full rounded-full border border-[var(--field-border)] bg-[var(--surface)] pl-6 pr-14 text-[16px] text-[var(--text)] shadow-[0_8px_30px_var(--input-shadow)] outline-none transition-shadow placeholder:text-[var(--muted)] focus:shadow-[0_10px_38px_var(--input-shadow)]"
          />
          <button
            type="submit"
            aria-label="送信"
            disabled={!message.trim() || !answerer || responding}
            className="absolute right-2 top-2 grid size-10 place-items-center rounded-full bg-[var(--primary)] text-[var(--on-primary)] transition-opacity disabled:opacity-25"
          >
            <ArrowUp className="size-[18px]" strokeWidth={2.2} />
          </button>
        </form>
        <p className="relative z-10 mx-auto mt-2 max-w-[760px] text-center text-xs text-[var(--muted)]">
          SodAIは息をするように嘘をつきます。安易に信用しないでください。
        </p>
      </div>
    </div>
  );
}
