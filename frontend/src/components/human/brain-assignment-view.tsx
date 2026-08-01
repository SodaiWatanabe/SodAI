"use client";

import {
  type FormEvent,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

import { calculateTurnScrollLayout } from "@/components/chat/thread-scroll-state";
import { useCreditBalance } from "@/components/credits/credit-balance-provider";
import { millisecondsUntilBrainAutoSubmit } from "@/components/human/brain-auto-submit";
import { BrainAssignmentDeadline } from "@/components/human/brain-assignment-deadline";
import { BrainConversation } from "@/components/human/brain-conversation";
import {
  isBrainSkipAllowed,
  millisecondsUntilBrainSkipCloses,
} from "@/components/human/brain-skip-window";
import { useBrainAnswerDraft } from "@/components/human/use-brain-answer-draft";
import { useHumanData } from "@/components/human/human-data-provider";
import { useTextareaAutosize } from "@/components/ui/use-textarea-autosize";
import type { HumanAssignment } from "@/lib/human/types";

export function BrainAssignmentView({
  assignment,
}: {
  assignment: HumanAssignment;
}) {
  const { refreshBalance } = useCreditBalance();
  const {
    answerClaim,
    busy,
    deadlineExpired,
    error,
    saveClaimDraft,
    skipClaim,
  } = useHumanData();
  const assignedViewRef = useRef<HTMLDivElement>(null);
  const answerRef = useRef<HTMLTextAreaElement>(null);
  const turnAnchorRef = useRef<HTMLElement>(null);
  const turnSpacerRef = useRef<HTMLDivElement>(null);
  const alignedRef = useRef(false);
  const [autoSubmitting, setAutoSubmitting] = useState(false);
  const [skipWindowClosed, setSkipWindowClosed] = useState(
    () => !isBrainSkipAllowed(assignment.skip_allowed_until),
  );
  const { answer, flushDraft, readAnswer, setAnswer } = useBrainAnswerDraft(
    assignment,
    saveClaimDraft,
  );

  useTextareaAutosize(answerRef, answer, assignment.claim_id);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const content = readAnswer().trim();
      void flushDraft();
      if (!content) return;

      setAutoSubmitting(true);
      void answerClaim(assignment.claim_id, content).then((answered) => {
        if (answered) {
          void refreshBalance();
          return;
        }
        setAutoSubmitting(false);
      });
    }, millisecondsUntilBrainAutoSubmit(assignment.deadline_at));
    return () => window.clearTimeout(timer);
  }, [
    answerClaim,
    assignment.claim_id,
    assignment.deadline_at,
    flushDraft,
    readAnswer,
    refreshBalance,
  ]);

  useEffect(() => {
    const remaining = millisecondsUntilBrainSkipCloses(
      assignment.skip_allowed_until,
    );
    if (remaining <= 0) return;
    const timer = window.setTimeout(() => setSkipWindowClosed(true), remaining);
    return () => window.clearTimeout(timer);
  }, [assignment.skip_allowed_until]);

  useLayoutEffect(() => {
    const assignedView = assignedViewRef.current;
    const turnAnchor = turnAnchorRef.current;
    const turnSpacer = turnSpacerRef.current;
    if (!assignedView || !turnAnchor || !turnSpacer) return;

    const currentSpacerHeight = turnSpacer.getBoundingClientRect().height;
    const assignedViewRect = assignedView.getBoundingClientRect();
    const turnAnchorRect = turnAnchor.getBoundingClientRect();
    const parsedScrollMarginTop = Number.parseFloat(
      window.getComputedStyle(turnAnchor).scrollMarginTop,
    );
    const layout = calculateTurnScrollLayout({
      containerHeight: assignedView.clientHeight,
      containerScrollTop: assignedView.scrollTop,
      containerTop: assignedViewRect.top,
      entryTop: turnAnchorRect.top,
      scrollHeight: assignedView.scrollHeight,
      scrollMarginTop: Number.isFinite(parsedScrollMarginTop)
        ? parsedScrollMarginTop
        : 0,
      spacerHeight: currentSpacerHeight,
    });

    turnSpacer.style.height = `${Math.ceil(layout.spacerHeight)}px`;
    if (!alignedRef.current) {
      assignedView.scrollTop = layout.scrollTop;
      alignedRef.current = true;
    }
  }, [answer]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const content = answer.trim();
    if (
      !content ||
      busy ||
      autoSubmitting ||
      deadlineExpired ||
      Date.parse(assignment.deadline_at) <= Date.now()
    ) {
      return;
    }

    void flushDraft();
    if (await answerClaim(assignment.claim_id, content)) {
      void refreshBalance();
    }
  }

  return (
    <div
      ref={assignedViewRef}
      className="flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain [overflow-anchor:none]"
    >
      <header className="sticky top-0 z-10 h-12 shrink-0 border-b border-[var(--separator)] bg-[var(--canvas)]">
        <div className="mx-auto flex h-full w-full max-w-[760px] items-center justify-between pl-12 pr-2 sm:pl-12 sm:pr-5 lg:mx-0 lg:max-w-none lg:px-1.5">
          <p className="truncate rounded-xl px-2.5 py-2 text-sm font-medium text-[var(--text)]">
            <span className="text-[var(--muted)]">You are</span>{" "}
            {assignment.answerer_name}
          </p>
          <BrainAssignmentDeadline deadlineAt={assignment.deadline_at} />
        </div>
      </header>

      <section aria-label="会話" className="relative isolate flex-1">
        <div className="relative z-10 mx-auto w-full max-w-[760px] px-5 pb-[max(2rem,env(safe-area-inset-bottom))] pt-10 sm:px-8">
          <BrainConversation
            context={assignment.context}
            turnAnchorRef={turnAnchorRef}
          >
            <form id="brain-answer-form" onSubmit={submit}>
              <label htmlFor="human-answer" className="sr-only">
                回答
              </label>
              <textarea
                ref={answerRef}
                id="human-answer"
                value={answer}
                rows={8}
                maxLength={32000}
                placeholder="回答を書く"
                readOnly={autoSubmitting || deadlineExpired}
                className="block min-h-[max(14rem,calc(100dvh-16rem))] w-full resize-none overflow-y-hidden border-0 bg-transparent p-0 text-[15px] leading-7 text-[var(--text)] outline-none placeholder:text-[var(--muted)]"
                onChange={(event) => setAnswer(event.target.value)}
              />
            </form>
          </BrainConversation>
          <div ref={turnSpacerRef} aria-hidden="true" className="h-0 shrink-0" />
        </div>
      </section>

      <div className="thread-composer sticky bottom-0 z-20 shrink-0 px-5 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 sm:px-8">
        {error ? (
          <p className="relative z-10 mx-auto mb-2 max-w-[760px] text-center text-xs text-[var(--danger-text)]">
            {error}
          </p>
        ) : null}
        <div className="chat-input relative z-10 mx-auto flex min-h-14 w-full max-w-[760px] items-center justify-end gap-2 overflow-hidden rounded-[28px] border border-[var(--field-border)] bg-[var(--surface)] p-2 text-[var(--text)] shadow-[0_8px_30px_var(--input-shadow)]">
          {skipWindowClosed ? null : (
            <button
              type="button"
              disabled={busy}
              className="h-10 rounded-full px-4 text-sm font-medium text-[var(--muted)] transition-colors hover:bg-[var(--hover)] disabled:opacity-50"
              onClick={() => {
                if (isBrainSkipAllowed(assignment.skip_allowed_until)) {
                  void skipClaim(assignment.claim_id);
                }
              }}
            >
              スキップ
            </button>
          )}
          <button
            type="submit"
            form="brain-answer-form"
            disabled={
              busy || autoSubmitting || deadlineExpired || !answer.trim()
            }
            className="h-10 rounded-full bg-[var(--primary)] px-5 text-sm font-medium text-[var(--on-primary)] transition-opacity disabled:opacity-40"
          >
            {autoSubmitting || (deadlineExpired && answer.trim())
              ? "送信中"
              : deadlineExpired
                ? "時間切れ"
                : "送信"}
          </button>
        </div>
      </div>
    </div>
  );
}
