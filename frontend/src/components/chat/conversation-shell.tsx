"use client";

import { ArrowUp } from "lucide-react";
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
import { ConversationViewport } from "@/components/chat/conversation-viewport";
import { useToast } from "@/components/ui/toast-provider";
import type {
  AvailableModel,
  ChatMessage,
  Conversation,
  RealtimeEvent,
} from "@/lib/chat/types";
import { useChatApi } from "@/lib/chat/use-chat-api";

type ConversationShellProps = {
  conversationId: string;
};

const STICK_TO_BOTTOM_THRESHOLD = 120;

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
  const { createTurn, getConversation } = useChatApi();
  const { models, patchConversation, subscribeRealtime } = useChatData();
  const { dismissToast, showToast } = useToast();
  const scrollRef = useRef<HTMLDivElement>(null);
  const initialScrollPositionedRef = useRef(false);
  const stickToBottomRef = useRef(true);
  const mountedRef = useRef(true);
  const realtimeRevisionRef = useRef(0);
  const refreshGenerationRef = useRef(0);
  const [conversation, setConversation] = useState<Conversation>();
  const [model, setModel] = useState<AvailableModel["id"]>();
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);

  const loadConversation = useCallback(
    () => getConversation(conversationId),
    [conversationId, getConversation],
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
          setModel(current.model);
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
      if (event.type === "conversation.updated" && event.data.title) {
        setConversation((current) =>
          current ? { ...current, title: event.data.title ?? current.title } : current,
        );
        return;
      }
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

    const unsubscribeRealtime = subscribeRealtime(applyRealtime);
    void syncConversation(false);
    return () => {
      cancelled = true;
      refreshGenerationRef.current += 1;
      unsubscribeRealtime();
      dismissToast("conversation-load");
    };
  }, [
    conversationId,
    dismissToast,
    loadConversation,
    showToast,
    subscribeRealtime,
  ]);

  useLayoutEffect(() => {
    const element = scrollRef.current;
    if (!element || !conversation) return;
    if (!initialScrollPositionedRef.current) {
      element.scrollTop = element.scrollHeight;
      initialScrollPositionedRef.current = true;
      stickToBottomRef.current = true;
      return;
    }
    if (stickToBottomRef.current) {
      element.scrollTo({ top: element.scrollHeight, behavior: "smooth" });
    }
  }, [conversation]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const input = message.trim();
    if (!input || !model || sending) return;
    stickToBottomRef.current = true;
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
    <div
      ref={scrollRef}
      className="flex min-h-0 flex-1 flex-col overflow-y-auto scroll-smooth"
      onScroll={(event) => {
        const element = event.currentTarget;
        const distanceFromBottom =
          element.scrollHeight - element.scrollTop - element.clientHeight;
        stickToBottomRef.current = distanceFromBottom <= STICK_TO_BOTTOM_THRESHOLD;
      }}
    >
      <ChatHeader
        disabled={sending}
        model={model}
        models={models}
        onModelChange={setModel}
        showPseudoBadge
      />

      <ConversationViewport conversation={conversation} loading={loading} />

      <div className="sticky bottom-0 z-20 shrink-0 bg-[var(--canvas)] px-5 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-8">
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
            disabled={!message.trim() || !model || sending}
            className="absolute right-2 top-2 grid size-10 place-items-center rounded-full bg-[var(--primary)] text-[var(--on-primary)] transition-opacity disabled:opacity-25"
          >
            <ArrowUp className="size-[18px]" strokeWidth={2.2} />
          </button>
        </form>
        <p className="mx-auto mt-2 max-w-[760px] text-center text-xs text-[var(--muted)]">
          SodAIは息をするように嘘をつきます。安易に信用しないでください。
        </p>
      </div>
    </div>
  );
}
