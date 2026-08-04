"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { useChatData } from "@/components/chat/chat-data-provider";
import { ChatHeader } from "@/components/chat/chat-header";
import { settleComposerFocus } from "@/components/chat/composer-focus";
import { HumanPrivacyDialog } from "@/components/chat/human-privacy-dialog";
import { shouldShowHumanPrivacyDialog } from "@/components/chat/human-privacy-transition";
import { MessageComposer } from "@/components/chat/message-composer";
import { ReasoningEffortSelector } from "@/components/chat/reasoning-effort-selector";
import {
  IDLE_RESPONSE_OPERATION,
  requestResponseCancellation,
  resolveCreatedExecution,
  responseOperationIsPending,
  type ResponseOperation,
} from "@/components/chat/response-operation";
import { useKeyboardShortcuts } from "@/components/preferences/keyboard-shortcuts-provider";
import { useToast } from "@/components/ui/toast-provider";
import { resolveChatMutationFailure } from "@/lib/chat/mutation-error";
import { resolveReasoningEffort } from "@/lib/chat/reasoning-effort";
import type {
  AvailableAnswerer,
  ReasoningEffort,
} from "@/lib/chat/types";
import { useChatApi } from "@/lib/chat/use-chat-api";
import { resolvePreferredAnswerer } from "@/lib/preferences/answerer";

type ChatShellProps = {
  greeting: string;
};

export function ChatShell(props: ChatShellProps) {
  const router = useRouter();
  const { cancelExecution, createThread } = useChatApi();
  const {
    answerers,
    preferredAnswerer,
    rememberAnswerer,
    upsertThread,
  } = useChatData();
  const { dismissToast, showToast } = useToast();
  const { shortcuts } = useKeyboardShortcuts();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const mountedRef = useRef(true);
  const [message, setMessage] = useState("");
  const [requestedReasoningEffort, setRequestedReasoningEffort] =
    useState<ReasoningEffort>();
  const [humanPrivacyDialogOpen, setHumanPrivacyDialogOpen] = useState(false);
  const operationRef = useRef<ResponseOperation>(IDLE_RESPONSE_OPERATION);
  const [operation, setOperationState] = useState<ResponseOperation>(
    IDLE_RESPONSE_OPERATION,
  );
  const answerer = resolvePreferredAnswerer(answerers, preferredAnswerer);
  const selectedAnswerer = answerers.find((option) => option.id === answerer);
  const reasoningEffort = resolveReasoningEffort(
    selectedAnswerer,
    requestedReasoningEffort,
  );

  function setOperation(next: ResponseOperation) {
    operationRef.current = next;
    setOperationState(next);
  }

  function stopResponse() {
    setOperation(requestResponseCancellation(operationRef.current));
  }

  function selectAnswerer(nextAnswerer: AvailableAnswerer["id"]) {
    const nextSelectedAnswerer = answerers.find(
      (option) => option.id === nextAnswerer,
    );
    rememberAnswerer(nextAnswerer);
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
    if (
      !input ||
      !answerer ||
      !reasoningEffort ||
      operationRef.current.kind !== "idle"
    ) {
      return;
    }
    setOperation({ kind: "creating" });
    settleComposerFocus(inputRef.current);
    dismissToast("thread-create");
    let created;
    try {
      created = await createThread(input, answerer, reasoningEffort);
    } catch (error) {
      if (!mountedRef.current) return;
      setOperation(IDLE_RESPONSE_OPERATION);
      const failure = resolveChatMutationFailure(
        error,
        "会話を始められませんでした。APIの接続を確認してください。",
      );
      showToast({
        id: "thread-create",
        ...failure,
      });
      requestAnimationFrame(() => inputRef.current?.focus());
      return;
    }

    if (!mountedRef.current) return;
    const nextOperation = resolveCreatedExecution(
      operationRef.current,
      created.response.execution.id,
    );
    setOperation(nextOperation);
    let thread = created.thread;
    if (nextOperation.kind === "cancelling") {
      try {
        thread = await cancelExecution(nextOperation.executionId);
      } catch {
        showToast({
          id: "response-cancel",
          message: "応答を停止できませんでした。会話画面でもう一度お試しください。",
          tone: "error",
        });
      }
    }
    if (!mountedRef.current) return;
    setOperation(IDLE_RESPONSE_OPERATION);
    upsertThread(thread);
    router.push(`/t/${created.thread.id}`);
  }

  return (
    <>
      <ChatHeader
        answerer={answerer}
        answerers={answerers}
        onAnswererChange={selectAnswerer}
      />
      {humanPrivacyDialogOpen ? (
        <HumanPrivacyDialog
          scope="message"
          onClose={() => setHumanPrivacyDialogOpen(false)}
        />
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
            action={
              operation.kind === "idle"
                ? {
                    kind: "send",
                    disabled: !message.trim() || !answerer || !reasoningEffort,
                  }
                : {
                    kind: "stop",
                    onStop: stopResponse,
                    pending: responseOperationIsPending(operation),
                  }
            }
            accessory={
              selectedAnswerer?.kind === "human" && reasoningEffort ? (
                <ReasoningEffortSelector
                  value={reasoningEffort}
                  options={selectedAnswerer.reasoning_efforts}
                  onChange={setRequestedReasoningEffort}
                />
              ) : undefined
            }
            ariaLabel="新しい会話"
            autoFocus
            className="relative lg:mt-7"
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
