"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { useChatData } from "@/components/chat/chat-data-provider";
import { ChatHeader } from "@/components/chat/chat-header";
import { settleComposerFocus } from "@/components/chat/composer-focus";
import { HumanPrivacyDialog } from "@/components/chat/human-privacy-dialog";
import { shouldShowHumanPrivacyDialog } from "@/components/chat/human-privacy-transition";
import { MessageComposer } from "@/components/chat/message-composer";
import { useKeyboardShortcuts } from "@/components/preferences/keyboard-shortcuts-provider";
import { useToast } from "@/components/ui/toast-provider";
import { isApiErrorStatus } from "@/lib/api/api-error";
import type { AvailableAnswerer } from "@/lib/chat/types";
import { useChatApi } from "@/lib/chat/use-chat-api";
import { INSUFFICIENT_CREDITS_MESSAGE } from "@/lib/credits/error";

type ChatShellProps = {
  greeting: string;
};

export function ChatShell(props: ChatShellProps) {
  const router = useRouter();
  const { createThread } = useChatApi();
  const { answerers, upsertThread } = useChatData();
  const { dismissToast, showToast } = useToast();
  const { shortcuts } = useKeyboardShortcuts();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const mountedRef = useRef(true);
  const [message, setMessage] = useState("");
  const [requestedAnswerer, setRequestedAnswerer] =
    useState<AvailableAnswerer["id"]>();
  const [submitting, setSubmitting] = useState(false);
  const [humanPrivacyDialogOpen, setHumanPrivacyDialogOpen] = useState(false);
  const answerer =
    requestedAnswerer ??
    answerers.find((availableAnswerer) => availableAnswerer.is_default)?.id ??
    answerers[0]?.id;
  const selectedAnswerer = answerers.find((option) => option.id === answerer);
  function selectAnswerer(nextAnswerer: AvailableAnswerer["id"]) {
    const nextSelectedAnswerer = answerers.find(
      (option) => option.id === nextAnswerer,
    );
    setRequestedAnswerer(nextAnswerer);
    if (shouldShowHumanPrivacyDialog(selectedAnswerer, nextSelectedAnswerer)) {
      setHumanPrivacyDialogOpen(true);
    }
  }

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
    } catch (error) {
      if (!mountedRef.current) return;
      setSubmitting(false);
      const insufficientCredits = isApiErrorStatus(error, 402);
      showToast({
        id: "thread-create",
        message: insufficientCredits
          ? INSUFFICIENT_CREDITS_MESSAGE
          : "会話を始められませんでした。APIの接続を確認してください。",
        tone: insufficientCredits ? "warning" : "error",
      });
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }

  return (
    <>
      <ChatHeader
        answerer={answerer}
        answerers={answerers}
        onAnswererChange={selectAnswerer}
      />
      {humanPrivacyDialogOpen ? (
        <HumanPrivacyDialog onClose={() => setHumanPrivacyDialogOpen(false)} />
      ) : null}
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
            sendShortcut={shortcuts.messageSend}
            textareaRef={inputRef}
            value={message}
          />
        </div>
      </section>
    </>
  );
}
