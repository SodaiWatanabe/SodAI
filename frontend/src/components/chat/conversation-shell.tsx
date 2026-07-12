"use client";

import { ArrowUp } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { useChatData } from "@/components/chat/chat-data-provider";
import { ChatHeader } from "@/components/chat/chat-header";
import { ConversationViewport } from "@/components/chat/conversation-viewport";
import { useToast } from "@/components/ui/toast-provider";
import {
  createRealtimeSocket,
  createTurn,
  getConversation,
} from "@/lib/chat/api";
import type {
  AvailableModel,
  ChatMessage,
  Conversation,
  RealtimeEvent,
} from "@/lib/chat/types";

type ConversationShellProps = {
  conversationId: string;
};

const REALTIME_RECONNECT_DELAY = 1200;
const REALTIME_TOAST_DELAY = 1800;

function mergeMessages(current: ChatMessage[], incoming: ChatMessage[]) {
  const byId = new Map(current.map((message) => [message.id, message]));
  for (const message of incoming) {
    const existing = byId.get(message.id);
    if (!existing) {
      byId.set(message.id, message);
      continue;
    }
    const existingTerminal = existing.status !== "streaming";
    const incomingTerminal = message.status !== "streaming";
    if (existingTerminal && !incomingTerminal) continue;
    if (!existingTerminal && incomingTerminal) {
      byId.set(message.id, {
        ...message,
        content:
          message.content.length >= existing.content.length
            ? message.content
            : existing.content,
      });
      continue;
    }
    if (!existingTerminal && !incomingTerminal) {
      byId.set(
        message.id,
        message.content.length >= existing.content.length ? message : existing,
      );
      continue;
    }
    byId.set(
      message.id,
      Date.parse(message.updated_at) >= Date.parse(existing.updated_at)
        ? message
        : existing,
    );
  }
  return [...byId.values()].sort((left, right) => left.ordinal - right.ordinal);
}

export function ConversationShell(props: ConversationShellProps) {
  const { conversationId } = props;
  const { models, patchConversation } = useChatData();
  const { dismissToast, showToast } = useToast();
  const scrollRef = useRef<HTMLDivElement>(null);
  const initialScrollPositionedRef = useRef(false);
  const mountedRef = useRef(true);
  const cursorRef = useRef(0);
  const realtimeRevisionRef = useRef(0);
  const refreshGenerationRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const realtimeToastTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [conversation, setConversation] = useState<Conversation>();
  const [model, setModel] = useState<AvailableModel["id"]>("archive");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);

  const loadConversation = useCallback(
    () => getConversation(conversationId),
    [conversationId],
  );

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      dismissToast("message-send");
    };
  }, [dismissToast]);

  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | undefined;

    function clearRealtimeToastDelay() {
      if (realtimeToastTimerRef.current) {
        clearTimeout(realtimeToastTimerRef.current);
        realtimeToastTimerRef.current = undefined;
      }
    }

    function scheduleRealtimeToast() {
      if (realtimeToastTimerRef.current) return;
      realtimeToastTimerRef.current = setTimeout(() => {
        realtimeToastTimerRef.current = undefined;
        if (cancelled) return;
        showToast({
          id: "realtime-connection",
          message: "リアルタイム接続を再試行しています。",
          tone: "warning",
          duration: null,
        });
      }, REALTIME_TOAST_DELAY);
    }

    async function syncConversation(showLoading: boolean) {
      if (cancelled) return;
      const generation = ++refreshGenerationRef.current;
      const realtimeRevision = realtimeRevisionRef.current;
      if (showLoading) setLoading(true);
      try {
        const current = await loadConversation();
        if (cancelled || generation !== refreshGenerationRef.current) return;
        setConversation((previous) => ({
          ...current,
          messages:
            previous?.id === current.id
              ? mergeMessages(previous.messages, current.messages)
              : current.messages,
        }));
        if (realtimeRevision === realtimeRevisionRef.current) {
          setModel(current.model as AvailableModel["id"]);
          setSending(Boolean(current.active_run));
        }
        dismissToast("conversation-load");
      } catch {
        if (cancelled || generation !== refreshGenerationRef.current) return;
        showToast({
          id: "conversation-load",
          message: "会話を読み込めませんでした。",
          tone: "error",
          duration: null,
          action: {
            label: "再試行",
            onClick: () => void syncConversation(true),
          },
        });
      } finally {
        if (!cancelled && generation === refreshGenerationRef.current) {
          setLoading(false);
        }
      }
    }

    function applyRealtime(event: RealtimeEvent) {
      if (event.conversation_id !== conversationId) return;
      realtimeRevisionRef.current += 1;
      cursorRef.current = Math.max(cursorRef.current, event.sequence);
      if (event.type === "message.created") {
        void syncConversation(false);
        return;
      }
      if (!event.data.message_id) return;
      if (event.type === "response.started" || event.type === "response.delta") {
        setSending(true);
      }
      setConversation((current) => {
        if (!current) return current;
        return {
          ...current,
          messages: current.messages.map((item) =>
            item.id === event.data.message_id
              ? {
                  ...item,
                  content: event.data.content ?? item.content,
                  status:
                    event.type === "response.completed"
                      ? "completed"
                      : event.type === "response.failed"
                        ? "failed"
                        : "streaming",
                }
              : item,
          ),
        };
      });
      if (event.type === "response.completed" || event.type === "response.failed") {
        setSending(false);
        void syncConversation(false);
      }
    }

    async function connect(after?: number) {
      try {
        const nextSocket = await createRealtimeSocket(after);
        if (cancelled) {
          nextSocket.close();
          return;
        }
        socket = nextSocket;
        socket.addEventListener("message", (messageEvent) => {
          const payload = JSON.parse(messageEvent.data as string) as
            | RealtimeEvent
            | { type: "ready" | "ping"; cursor?: number };
          if (payload.type === "ready") {
            cursorRef.current = Math.max(cursorRef.current, payload.cursor ?? 0);
            clearRealtimeToastDelay();
            dismissToast("realtime-connection");
          } else if (payload.type !== "ping" && "sequence" in payload) {
            applyRealtime(payload);
          }
        });
        socket.addEventListener("close", () => {
          if (!cancelled) {
            scheduleRealtimeToast();
            reconnectTimerRef.current = setTimeout(
              () => void connect(cursorRef.current),
              REALTIME_RECONNECT_DELAY,
            );
          }
        });
      } catch {
        if (!cancelled) {
          scheduleRealtimeToast();
          reconnectTimerRef.current = setTimeout(
            () => void connect(cursorRef.current),
            REALTIME_RECONNECT_DELAY,
          );
        }
      }
    }

    void syncConversation(false);
    void connect();
    return () => {
      cancelled = true;
      refreshGenerationRef.current += 1;
      socket?.close();
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      clearRealtimeToastDelay();
      dismissToast("conversation-load");
      dismissToast("realtime-connection");
    };
  }, [conversationId, dismissToast, loadConversation, showToast]);

  useEffect(() => {
    const element = scrollRef.current;
    if (!element || !conversation) return;
    if (!initialScrollPositionedRef.current) {
      element.scrollTop = 0;
      initialScrollPositionedRef.current = true;
      return;
    }
    element.scrollTo({ top: element.scrollHeight, behavior: "smooth" });
  }, [conversation]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const input = message.trim();
    if (!input || sending) return;
    setMessage("");
    setSending(true);
    dismissToast("message-send");
    try {
      const created = await createTurn(conversationId, input, model);
      if (!mountedRef.current) return;
      setConversation((current) =>
        current
          ? {
              ...current,
              model,
              messages: mergeMessages(current.messages, created.conversation.messages),
              active_run: created.run,
            }
          : current,
      );
      patchConversation(conversationId, {
        last_activity_at: new Date().toISOString(),
        model,
      });
    } catch {
      if (!mountedRef.current) return;
      setMessage(input);
      setSending(false);
      showToast({
        id: "message-send",
        message: "送信できませんでした。もう一度お試しください。",
        tone: "error",
      });
    }
  }

  return (
    <>
      <ChatHeader
        disabled={sending}
        model={model}
        models={models}
        onModelChange={setModel}
        showPseudoBadge
      />

      <ConversationViewport
        conversation={conversation}
        loading={loading}
        scrollRef={scrollRef}
      />

      <div className="shrink-0 bg-[linear-gradient(to_top,var(--canvas)_75%,transparent)] px-5 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-5 sm:px-8">
        <form
          onSubmit={submit}
          className="relative mx-auto max-w-[760px]"
        >
          <label htmlFor="conversation-message" className="sr-only">
            対話を続ける
          </label>
          <input
            id="conversation-message"
            type="text"
            value={message}
            disabled={sending}
            placeholder="対話を続ける"
            autoComplete="off"
            spellCheck="true"
            onChange={(event) => setMessage(event.target.value)}
            className="chat-input block h-14 w-full rounded-full border border-[var(--field-border)] bg-[var(--surface)] pl-6 pr-14 text-[16px] text-[var(--text)] shadow-[0_8px_30px_var(--input-shadow)] outline-none transition-shadow placeholder:text-[var(--muted)] focus:shadow-[0_10px_38px_var(--input-shadow)]"
          />
          <button
            type="submit"
            aria-label="送信"
            disabled={!message.trim() || sending}
            className="absolute right-2 top-2 grid size-10 place-items-center rounded-full bg-[var(--primary)] text-[var(--on-primary)] transition-opacity disabled:opacity-25"
          >
            <ArrowUp className="size-[18px]" strokeWidth={2.2} />
          </button>
        </form>
        <p className="mx-auto mt-2 max-w-[760px] text-center text-[10px] text-[var(--muted)]">
          疑似AIによる基盤確認用の応答です
        </p>
      </div>
    </>
  );
}
