"use client";

import { ArrowUp } from "lucide-react";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { useChatData } from "@/components/chat/chat-data-provider";
import { ChatHeader } from "@/components/chat/chat-header";
import { settleComposerFocus } from "@/components/chat/composer-focus";
import { useToast } from "@/components/ui/toast-provider";
import type { AvailableModel } from "@/lib/chat/types";
import { useChatApi } from "@/lib/chat/use-chat-api";

type ChatShellProps = {
  greeting: string;
};

export function ChatShell(props: ChatShellProps) {
  const router = useRouter();
  const { createConversation } = useChatApi();
  const { models, upsertConversation } = useChatData();
  const { dismissToast, showToast } = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const mountedRef = useRef(true);
  const [message, setMessage] = useState("");
  const [requestedModel, setRequestedModel] = useState<AvailableModel["id"]>();
  const [submitting, setSubmitting] = useState(false);
  const model =
    requestedModel ??
    models.find((availableModel) => availableModel.is_default)?.id ??
    models[0]?.id;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      dismissToast("conversation-create");
    };
  }, [dismissToast]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const input = message.trim();
    if (!input || !model || submitting) return;
    setSubmitting(true);
    settleComposerFocus(inputRef.current);
    dismissToast("conversation-create");
    try {
      const created = await createConversation(input, model);
      upsertConversation(created.conversation);
      if (!mountedRef.current) return;
      router.push(`/c/${created.conversation.id}`);
    } catch {
      if (!mountedRef.current) return;
      setSubmitting(false);
      showToast({
        id: "conversation-create",
        message: "会話を始められませんでした。APIの接続を確認してください。",
        tone: "error",
      });
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }

  return (
    <>
      <ChatHeader
        model={model}
        models={models}
        onModelChange={setRequestedModel}
      />
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
              autoFocus
              onChange={(event) => setMessage(event.target.value)}
              placeholder="話しかけてください"
              autoComplete="off"
              spellCheck="true"
              className="chat-input block h-14 w-full rounded-full border border-[var(--field-border)] bg-[var(--surface)] pl-6 pr-14 text-[16px] text-[var(--text)] shadow-[0_8px_30px_var(--input-shadow)] outline-none transition-shadow placeholder:text-[var(--muted)] focus:shadow-[0_10px_38px_var(--input-shadow)]"
            />
            <button
              type="submit"
              aria-label="送信"
              disabled={!message.trim() || !model || submitting}
              className="absolute right-2 top-2 grid size-10 place-items-center rounded-full bg-[var(--primary)] text-[var(--on-primary)] transition-opacity disabled:opacity-25"
            >
              <ArrowUp className="size-[18px]" strokeWidth={2.2} />
            </button>
          </form>
        </div>
      </section>
    </>
  );
}
