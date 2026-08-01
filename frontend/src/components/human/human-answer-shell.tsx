"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { useChatAuth } from "@/components/chat/chat-auth-context";
import { calculateTurnScrollLayout } from "@/components/chat/thread-scroll-state";
import { getConversationMessageLayout } from "@/components/conversation/conversation-layout";
import { ConversationMessage } from "@/components/conversation/conversation-message";
import { BrainConversation } from "@/components/human/brain-conversation";
import { BrainLobby } from "@/components/human/brain-lobby";
import { useHumanData } from "@/components/human/human-data-provider";
import { IOSSpinner } from "@/components/ui/ios-spinner";
import { isApiErrorStatus } from "@/lib/api/api-error";
import type { HumanAnswerDetail } from "@/lib/human/types";

export function HumanAnswerShell({ executionId }: { executionId: string }) {
  const { authenticated, openAuth } = useChatAuth();
  const { getAnswer, state } = useHumanData();
  const [answer, setAnswer] = useState<HumanAnswerDetail>();
  const [error, setError] = useState<string>();
  const [loadVersion, setLoadVersion] = useState(0);
  const viewportRef = useRef<HTMLDivElement>(null);
  const turnAnchorRef = useRef<HTMLElement>(null);
  const turnSpacerRef = useRef<HTMLDivElement>(null);
  const alignedExecutionIdRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (!authenticated || state?.status === "assigned") return;
    let cancelled = false;
    void getAnswer(executionId).then(
      (loaded) => {
        if (!cancelled) setAnswer(loaded);
      },
      (loadError: unknown) => {
        if (cancelled) return;
        setError(
          isApiErrorStatus(loadError, 404)
            ? "この回答履歴は見つかりませんでした。"
            : "回答履歴を読み込めませんでした。",
        );
      },
    );
    return () => {
      cancelled = true;
    };
  }, [authenticated, executionId, getAnswer, loadVersion, state?.status]);

  useLayoutEffect(() => {
    const viewport = viewportRef.current;
    const turnAnchor = turnAnchorRef.current;
    const turnSpacer = turnSpacerRef.current;
    if (!answer || !viewport || !turnAnchor || !turnSpacer) {
      alignedExecutionIdRef.current = undefined;
      return;
    }
    if (alignedExecutionIdRef.current === answer.execution_id) return;
    const viewportRect = viewport.getBoundingClientRect();
    const turnAnchorRect = turnAnchor.getBoundingClientRect();
    const parsedScrollMarginTop = Number.parseFloat(
      window.getComputedStyle(turnAnchor).scrollMarginTop,
    );
    const layout = calculateTurnScrollLayout({
      containerHeight: viewport.clientHeight,
      containerScrollTop: viewport.scrollTop,
      containerTop: viewportRect.top,
      entryTop: turnAnchorRect.top,
      scrollHeight: viewport.scrollHeight,
      scrollMarginTop: Number.isFinite(parsedScrollMarginTop)
        ? parsedScrollMarginTop
        : 0,
      spacerHeight: turnSpacer.getBoundingClientRect().height,
    });
    turnSpacer.style.height = `${Math.ceil(layout.spacerHeight)}px`;
    viewport.scrollTop = layout.scrollTop;
    alignedExecutionIdRef.current = answer.execution_id;
  }, [answer]);

  if (!authenticated) {
    return <BrainLobby mode="signed-out" onAction={openAuth} />;
  }

  if (state?.status === "assigned") {
    return (
      <div className="grid flex-1 place-items-center">
        <IOSSpinner label="回答画面へ移動中" />
      </div>
    );
  }

  if (!answer) {
    return (
      <div className="grid flex-1 place-items-center px-6 text-center">
        {error ? (
          <div>
            <p className="text-sm text-[var(--muted)]">{error}</p>
            {!error.includes("見つかりません") ? (
              <button
                type="button"
                className="mt-3 text-sm font-medium text-[var(--text)]"
                onClick={() => {
                  setError(undefined);
                  setLoadVersion((version) => version + 1);
                }}
              >
                再試行
              </button>
            ) : null}
          </div>
        ) : (
          <IOSSpinner label="回答履歴を読み込み中" />
        )}
      </div>
    );
  }

  return (
    <div
      ref={viewportRef}
      className="flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain [overflow-anchor:none]"
    >
      <header className="sticky top-0 z-10 h-12 shrink-0 border-b border-[var(--separator)] bg-[var(--canvas)]">
        <div className="mx-auto flex h-full w-full max-w-[760px] items-center pl-12 pr-2 sm:pl-12 sm:pr-5 lg:mx-0 lg:max-w-none lg:px-1.5">
          <p className="truncate rounded-xl px-2.5 py-2 text-sm font-medium text-[var(--text)]">
            <span className="text-[var(--muted)]">You were</span>{" "}
            {answer.answerer_name}
          </p>
        </div>
      </header>

      <section aria-label="回答履歴" className="relative isolate flex-1">
        <div className="relative z-10 mx-auto w-full max-w-[760px] px-5 pb-[max(2rem,env(safe-area-inset-bottom))] pt-10 sm:px-8">
          <BrainConversation
            context={answer.context}
            turnAnchorRef={turnAnchorRef}
          >
            <ConversationMessage
              {...getConversationMessageLayout("model", "answerer")}
            >
              {answer.answer}
            </ConversationMessage>
          </BrainConversation>
          <div ref={turnSpacerRef} aria-hidden="true" className="h-0" />
        </div>
      </section>
    </div>
  );
}
