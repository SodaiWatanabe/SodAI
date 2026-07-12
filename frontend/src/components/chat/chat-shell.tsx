"use client";

import { ArrowUp, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { ChatFrame } from "@/components/chat/chat-frame";
import type { SidebarUser } from "@/components/chat/sidebar-account";
import {
  createConversation,
  listConversations,
  listModels,
} from "@/lib/chat/api";
import type { AvailableModel, ConversationSummary } from "@/lib/chat/types";

type ChatShellProps = {
  greeting: string;
  googleAuthEnabled: boolean;
  initialDesktopSidebarCollapsed: boolean;
  initialGoogleAuthError: boolean;
  initialUser: SidebarUser | null;
};

export function ChatShell(props: ChatShellProps) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState("");
  const [model, setModel] = useState<AvailableModel["id"]>("archive");
  const [models, setModels] = useState<AvailableModel[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    let cancelled = false;
    async function loadSidebar() {
      try {
        const history = await listConversations();
        const availableModels = await listModels();
        if (!cancelled) {
          setConversations(history);
          setModels(availableModels);
          setModel(availableModels[0]?.id ?? "archive");
        }
      } catch {
        if (!cancelled) {
          setError("APIを起動すると会話を始められます。");
        }
      }
    }
    void loadSidebar();
    return () => {
      cancelled = true;
    };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const input = message.trim();
    if (!input || submitting) return;
    setSubmitting(true);
    setError(undefined);
    try {
      const created = await createConversation(input, model);
      setConversations((current) => [
        created.conversation,
        ...current.filter((item) => item.id !== created.conversation.id),
      ]);
      router.push(`/c/${created.conversation.id}`);
    } catch {
      setSubmitting(false);
      setError("会話を始められませんでした。APIの接続を確認してください。");
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }

  return (
    <ChatFrame {...props} conversations={conversations}>
      <section className="mx-auto grid w-full max-w-[760px] flex-1 grid-rows-[1fr_auto] px-5 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-8 lg:flex lg:flex-col lg:justify-center lg:pb-16">
        <h1 className="self-center -translate-y-[3vh] text-center text-2xl font-normal tracking-[-0.04em] text-[var(--text)] sm:text-[28px] lg:hidden">
          {props.greeting}
        </h1>
        <div className="w-full lg:-translate-y-[7vh]">
          <h1 className="hidden text-center text-[28px] font-normal tracking-[-0.04em] text-[var(--text)] lg:block">
            {props.greeting}
          </h1>
          <form
            className="relative lg:mt-7"
            onSubmit={submit}
            aria-label="新しい会話"
          >
            <label htmlFor="chat-message" className="sr-only">
              SodAIへのメッセージ
            </label>
            <input
              ref={inputRef}
              id="chat-message"
              type="text"
              value={message}
              disabled={submitting}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="話しかけてください"
              autoComplete="off"
              spellCheck="true"
              className="chat-input block h-14 w-full rounded-full border border-[var(--field-border)] bg-[var(--surface)] pl-6 pr-14 text-[16px] text-[var(--text)] shadow-[0_8px_30px_var(--input-shadow)] outline-none transition-shadow placeholder:text-[var(--muted)] focus:shadow-[0_10px_38px_var(--input-shadow)]"
            />
            <button
              type="submit"
              aria-label="送信"
              disabled={!message.trim() || submitting}
              className="absolute right-2 top-2 grid size-10 place-items-center rounded-full bg-[var(--primary)] text-[var(--on-primary)] transition-[transform,opacity] hover:scale-[1.03] disabled:opacity-25"
            >
              <ArrowUp className="size-[18px]" strokeWidth={2.2} />
            </button>
          </form>
          <div className="mt-3 flex min-h-7 items-center justify-center">
            {models.length > 1 ? (
              <label className="flex items-center gap-1.5 text-xs text-[var(--muted)]">
                <Sparkles className="size-3.5" />
                <span className="sr-only">モデル</span>
                <select
                  value={model}
                  onChange={(event) =>
                    setModel(event.target.value as AvailableModel["id"])
                  }
                  className="cursor-pointer appearance-none bg-transparent pr-1 outline-none"
                >
                  {models.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <span className="flex items-center gap-1.5 text-xs text-[var(--muted)]">
                <Sparkles className="size-3.5" /> Archive
              </span>
            )}
          </div>
          {error ? (
            <p role="status" className="mt-2 text-center text-xs text-[var(--danger-text)]">
              {error}
            </p>
          ) : null}
        </div>
      </section>
    </ChatFrame>
  );
}
