"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { useChatData } from "@/components/chat/chat-data-provider";
import { ChatHeader } from "@/components/chat/chat-header";
import { settleComposerFocus } from "@/components/chat/composer-focus";
import { MessageComposer } from "@/components/chat/message-composer";
import { useMessageSendPreference } from "@/components/preferences/message-send-preference-provider";
import { useToast } from "@/components/ui/toast-provider";
import type { AvailableAnswerer } from "@/lib/chat/types";
import { useChatApi } from "@/lib/chat/use-chat-api";

type ChatShellProps = {
  greeting: string;
};

export function ChatShell(props: ChatShellProps) {
  const router = useRouter();
  const { createThread } = useChatApi();
  const { answerers, upsertThread } = useChatData();
  const { dismissToast, showToast } = useToast();
  const { preference: messageSendPreference } = useMessageSendPreference();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const mountedRef = useRef(true);
  const [message, setMessage] = useState("");
  const [requestedAnswerer, setRequestedAnswerer] =
    useState<AvailableAnswerer["id"]>();
  const [submitting, setSubmitting] = useState(false);
  const answerer =
    requestedAnswerer ??
    answerers.find((availableAnswerer) => availableAnswerer.is_default)?.id ??
    answerers[0]?.id;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      dismissToast("thread-create");
    };
  }, [dismissToast]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const input = message.trim();
    if (!input || !answerer || submitting) return;
    setSubmitting(true);
    settleComposerFocus(inputRef.current);
    dismissToast("thread-create");
    try {
      const created = await createThread(input, answerer);
      upsertThread(created.thread);
      if (!mountedRef.current) return;
      router.push(`/t/${created.thread.id}`);
    } catch {
      if (!mountedRef.current) return;
      setSubmitting(false);
      showToast({
        id: "thread-create",
        message: "会話を始められませんでした。APIの接続を確認してください。",
        tone: "error",
      });
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }

  return (
    <>
      <ChatHeader
        answerer={answerer}
        answerers={answerers}
        onAnswererChange={setRequestedAnswerer}
      />
      <section className="mx-auto grid w-full max-w-[760px] flex-1 grid-rows-[1fr_auto] px-5 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-8 lg:flex lg:flex-col lg:justify-center lg:pb-16">
        <h1 className="self-center -translate-y-[3vh] text-center text-2xl font-normal tracking-[-0.04em] text-[var(--text)] sm:text-[28px] lg:hidden">
          {props.greeting}
        </h1>
        <div className="w-full lg:-translate-y-[7vh]">
          <h1 className="hidden text-center text-[28px] font-normal tracking-[-0.04em] text-[var(--text)] lg:block">
            {props.greeting}
          </h1>
          <MessageComposer
            ariaLabel="新しい会話"
            autoFocus
            className="relative lg:mt-7"
            disabled={!message.trim() || !answerer || submitting}
            inputId="chat-message"
            inputLabel="SodAIへのメッセージ"
            onChange={setMessage}
            onSubmit={submit}
            placeholder="話しかけてください"
            sendPreference={messageSendPreference}
            textareaRef={inputRef}
            value={message}
          />
        </div>
      </section>
    </>
  );
}
