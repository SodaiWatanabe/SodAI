"use client";

import { ArrowUp, RotateCw, Sparkles } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { ChatFrame } from "@/components/chat/chat-frame";
import type { SidebarUser } from "@/components/chat/sidebar-account";
import {
  createRealtimeSocket,
  createTurn,
  getConversation,
  listConversations,
  listModels,
} from "@/lib/chat/api";
import type {
  AvailableModel,
  ChatMessage,
  Conversation,
  ConversationSummary,
  RealtimeEvent,
} from "@/lib/chat/types";

type ConversationShellProps = {
  conversationId: string;
  googleAuthEnabled: boolean;
  initialDesktopSidebarCollapsed: boolean;
  initialGoogleAuthError: boolean;
  initialUser: SidebarUser | null;
};

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
  const scrollRef = useRef<HTMLDivElement>(null);
  const cursorRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [conversation, setConversation] = useState<Conversation>();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [models, setModels] = useState<AvailableModel[]>([]);
  const [model, setModel] = useState<AvailableModel["id"]>("archive");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string>();

  const refreshConversation = useCallback(async () => {
    const current = await getConversation(conversationId);
    setConversation((previous) => ({
      ...current,
      messages: previous?.id === current.id
        ? mergeMessages(previous.messages, current.messages)
        : current.messages,
    }));
    setModel(current.model as AvailableModel["id"]);
    setSending(Boolean(current.active_run));
  }, [conversationId]);

  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | undefined;

    function applyRealtime(event: RealtimeEvent) {
      if (event.conversation_id !== conversationId) return;
      cursorRef.current = Math.max(cursorRef.current, event.sequence);
      if (event.type === "message.created") {
        void refreshConversation();
        return;
      }
      if (!event.data.message_id) return;
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
        void refreshConversation();
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
            setError(undefined);
          } else if (payload.type !== "ping" && "sequence" in payload) {
            applyRealtime(payload);
          }
        });
        socket.addEventListener("close", () => {
          if (!cancelled) {
            reconnectTimerRef.current = setTimeout(
              () => void connect(cursorRef.current),
              1200,
            );
          }
        });
        await refreshConversation();
      } catch {
        if (!cancelled) {
          setError("リアルタイム接続を再試行しています。");
          reconnectTimerRef.current = setTimeout(
            () => void connect(cursorRef.current),
            1200,
          );
        }
      }
    }

    async function initialize() {
      try {
        const history = await listConversations();
        const availableModels = await listModels();
        if (cancelled) return;
        setConversations(history);
        setModels(availableModels);
        await connect();
      } catch {
        if (!cancelled) setError("会話を読み込めませんでした。");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void initialize();
    return () => {
      cancelled = true;
      socket?.close();
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    };
  }, [conversationId, refreshConversation]);

  useEffect(() => {
    const element = scrollRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [conversation?.messages]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const input = message.trim();
    if (!input || sending) return;
    setMessage("");
    setSending(true);
    setError(undefined);
    try {
      const created = await createTurn(conversationId, input, model);
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
      setConversations((current) =>
        current.map((item) =>
          item.id === conversationId
            ? { ...item, last_activity_at: new Date().toISOString(), model }
            : item,
        ),
      );
    } catch {
      setMessage(input);
      setSending(false);
      setError("送信できませんでした。もう一度お試しください。");
    }
  }

  return (
    <ChatFrame
      {...props}
      activeConversationId={conversationId}
      conversations={conversations}
    >
      <header className="flex h-12 shrink-0 items-center justify-center border-b border-[var(--separator)] px-12">
        <label className="flex items-center gap-1.5 text-[13px] font-medium text-[var(--muted)]">
          <Sparkles className="size-3.5" />
          <span className="sr-only">モデル</span>
          <select
            value={model}
            disabled={sending}
            onChange={(event) => setModel(event.target.value as AvailableModel["id"])}
            className="cursor-pointer appearance-none bg-transparent pr-1 text-[var(--text)] outline-none disabled:opacity-50"
          >
            {(models.length ? models : [{ id: "archive", name: "Archive", description: "" }]).map(
              (item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ),
            )}
          </select>
          <span className="rounded-full bg-[var(--control-background)] px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-[var(--muted)]">
            Pseudo
          </span>
        </label>
      </header>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto scroll-smooth">
        <div className="mx-auto flex min-h-full w-full max-w-[760px] flex-col px-5 py-10 sm:px-8">
          {loading ? (
            <div className="grid flex-1 place-items-center text-[var(--muted)]">
              <RotateCw className="size-4 animate-spin" />
            </div>
          ) : conversation ? (
            <div className="mt-auto space-y-8">
              {conversation.messages.map((item) => (
                <article
                  key={item.id}
                  className={item.speaker === "partner" ? "flex justify-end" : "flex justify-start"}
                >
                  <div
                    className={
                      item.speaker === "partner"
                        ? "max-w-[82%] rounded-[22px] bg-[var(--field)] px-4 py-2.5 text-[15px] leading-6 text-[var(--text)]"
                        : "max-w-[92%] whitespace-pre-wrap text-[15px] leading-7 text-[var(--text)]"
                    }
                  >
                    {item.content}
                    {item.speaker === "sodai" && item.status === "streaming" ? (
                      <span className="ml-1 inline-block size-1.5 animate-pulse rounded-full bg-[var(--muted)] align-middle" />
                    ) : null}
                    {item.status === "failed" ? (
                      <span className="text-sm text-[var(--danger-text)]">
                        応答を完了できませんでした。
                      </span>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="grid flex-1 place-items-center text-sm text-[var(--muted)]">
              この会話を表示できません。
            </div>
          )}
        </div>
      </div>

      <div className="shrink-0 bg-[linear-gradient(to_top,var(--canvas)_75%,transparent)] px-5 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-5 sm:px-8">
        <form
          onSubmit={submit}
          className="relative mx-auto max-w-[760px] rounded-[26px] border border-[var(--field-border)] bg-[var(--surface)] shadow-[0_7px_26px_var(--input-shadow)]"
        >
          <label htmlFor="conversation-message" className="sr-only">
            対話を続ける
          </label>
          <textarea
            id="conversation-message"
            rows={1}
            value={message}
            disabled={sending}
            placeholder="対話を続ける"
            onChange={(event) => setMessage(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            className="block max-h-40 min-h-13 w-full resize-none bg-transparent py-3.5 pl-5 pr-14 text-[15px] leading-6 outline-none placeholder:text-[var(--muted)] disabled:opacity-60"
          />
          <button
            type="submit"
            aria-label="送信"
            disabled={!message.trim() || sending}
            className="absolute bottom-1.5 right-1.5 grid size-10 place-items-center rounded-full bg-[var(--primary)] text-[var(--on-primary)] transition-[transform,opacity] hover:scale-[1.03] disabled:opacity-25"
          >
            <ArrowUp className="size-[18px]" strokeWidth={2.2} />
          </button>
        </form>
        <p className="mx-auto mt-2 max-w-[760px] text-center text-[10px] text-[var(--muted)]">
          疑似AIによる基盤確認用の応答です
        </p>
        {error ? (
          <p role="status" className="mt-1 text-center text-xs text-[var(--danger-text)]">
            {error}
          </p>
        ) : null}
      </div>
    </ChatFrame>
  );
}
