"use client";

import { ArrowDown } from "lucide-react";
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
import { settleComposerFocus } from "@/components/chat/composer-focus";
import {
  createHumanResponseDeliveryPlan,
  isLiveHumanResponseCompletion,
} from "@/components/chat/human-response-delivery";
import { HumanPrivacyDialog } from "@/components/chat/human-privacy-dialog";
import { shouldShowHumanPrivacyDialog } from "@/components/chat/human-privacy-transition";
import { MessageComposer } from "@/components/chat/message-composer";
import {
  IDLE_RESPONSE_OPERATION,
  requestResponseCancellation,
  resolveCreatedExecution,
  resolveTerminalExecution,
  responseOperationIsPending,
  type ResponseOperation,
} from "@/components/chat/response-operation";
import { ResponseAmbient } from "@/components/chat/response-ambient";
import {
  mergeExecutionSnapshot,
  reduceThreadRealtime,
} from "@/components/chat/thread-realtime";
import { ThreadViewport } from "@/components/chat/thread-viewport";
import type { ResponsePresentation } from "@/components/chat/thread-display-entries";
import { useThreadSearchNavigationTarget } from "@/components/chat/thread-search-navigation";
import { useThreadAutoScroll } from "@/components/chat/use-thread-auto-scroll";
import { useKeyboardShortcuts } from "@/components/preferences/keyboard-shortcuts-provider";
import { useToast } from "@/components/ui/toast-provider";
import type {
  AvailableAnswerer,
  RealtimeEvent,
  Thread,
  ThreadEntry,
} from "@/lib/chat/types";
import { isApiErrorStatus } from "@/lib/api/api-error";
import { useChatApi } from "@/lib/chat/use-chat-api";
import { INSUFFICIENT_CREDITS_MESSAGE } from "@/lib/credits/error";

type ThreadShellProps = {
  threadId: string;
  targetEntryId?: string;
};

type TurnAnchor = {
  entryId: string;
  threadId: string;
};

function mergeEntries(current: ThreadEntry[], incoming: ThreadEntry[]) {
  const byId = new Map(current.map((entry) => [entry.id, entry]));
  for (const entry of incoming) byId.set(entry.id, entry);
  return [...byId.values()].sort((left, right) => left.ordinal - right.ordinal);
}

function isResponding(thread?: Thread) {
  const status = thread?.latest_response?.status;
  return status === "queued" || status === "running";
}

export function ThreadShell({ threadId, targetEntryId }: ThreadShellProps) {
  const { cancelExecution, createResponse, getThread } = useChatApi();
  const searchNavigationTarget = useThreadSearchNavigationTarget();
  const {
    answerers,
    patchThread,
    realtimeReadyRevision,
    subscribeRealtime,
  } = useChatData();
  const { dismissToast, showToast } = useToast();
  const { shortcuts } = useKeyboardShortcuts();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const threadRef = useRef<Thread | undefined>(undefined);
  const answererInitializedRef = useRef(false);
  const mountedRef = useRef(true);
  const refreshGenerationRef = useRef(0);
  const pendingExecutionSyncRef = useRef<string | undefined>(undefined);
  const executionSyncDirtyRef = useRef(false);
  const targetEntryIdRef = useRef(targetEntryId);
  const scrolledTargetRef = useRef<string | undefined>(undefined);
  const positionedTurnRef = useRef<string | undefined>(undefined);
  const operationRef = useRef<ResponseOperation>(IDLE_RESPONSE_OPERATION);
  const [thread, setThreadState] = useState<Thread>();
  const [turnAnchor, setTurnAnchor] = useState<TurnAnchor>();
  const [answerer, setAnswerer] = useState<AvailableAnswerer["id"]>();
  const [humanPrivacyDialogOpen, setHumanPrivacyDialogOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [humanResponsePresentation, setHumanResponsePresentation] =
    useState<ResponsePresentation>();
  const [operation, setOperationState] = useState<ResponseOperation>(
    IDLE_RESPONSE_OPERATION,
  );
  const responding = operation.kind !== "idle" || isResponding(thread);
  const selectedAnswerer = answerers.find((option) => option.id === answerer);
  const latestResponse = thread?.latest_response;
  const respondingAnswererId =
    latestResponse?.status === "queued" || latestResponse?.status === "running"
      ? latestResponse.requested_answerer
      : operation.kind === "creating" ||
          operation.kind === "waiting-for-execution-to-cancel"
        ? answerer
        : undefined;
  const respondingAnswerer = answerers.find(
    (option) => option.id === respondingAnswererId,
  );
  const activeSearchTarget =
    targetEntryId &&
    searchNavigationTarget?.threadId === threadId &&
    searchNavigationTarget.entryId === targetEntryId
      ? searchNavigationTarget
      : undefined;
  const targetSearchQuery = activeSearchTarget?.query;
  const turnAnchorEntryId =
    turnAnchor?.threadId === threadId ? turnAnchor.entryId : undefined;
  const {
    anchorTurn,
    containerRef,
    messageListRef,
    footerRef,
    handleComposerBlur,
    handleComposerInteraction,
    handleScroll,
    handleScrollKeyDown,
    handleScrollPointerDown,
    handleUserScrollIntent,
    pinToBottom,
    scrollToEntry,
    scrollToBottom,
    showScrollToBottom,
    turnAnchorRef,
    turnSpacerRef,
  } = useThreadAutoScroll({ ready: Boolean(thread), resetKey: threadId });

  const updateThread = useCallback(
    (update: (current?: Thread) => Thread | undefined) => {
      const next = update(threadRef.current);
      threadRef.current = next;
      setThreadState(next);
    },
    [],
  );

  const loadThread = useCallback(() => getThread(threadId), [getThread, threadId]);

  function setOperation(next: ResponseOperation) {
    operationRef.current = next;
    setOperationState(next);
  }

  function selectAnswerer(nextAnswerer: AvailableAnswerer["id"]) {
    const nextSelectedAnswerer = answerers.find(
      (option) => option.id === nextAnswerer,
    );
    setAnswerer(nextAnswerer);
    if (shouldShowHumanPrivacyDialog(selectedAnswerer, nextSelectedAnswerer)) {
      setHumanPrivacyDialogOpen(true);
    }
  }

  async function cancelResponse(executionId: string) {
    setOperation({ kind: "cancelling", executionId });
    dismissToast("response-cancel");
    try {
      const cancelledThread = await cancelExecution(executionId);
      if (!mountedRef.current || cancelledThread.id !== threadId) return;
      updateThread((current) =>
        mergeExecutionSnapshot(current, cancelledThread, executionId),
      );
      patchThread(threadId, {
        answerer: cancelledThread.answerer,
        last_activity_at: cancelledThread.last_activity_at,
        revision: cancelledThread.revision,
        updated_at: cancelledThread.updated_at,
      });
    } catch {
      if (!mountedRef.current) return;
      if (
        operationRef.current.kind !== "cancelling" ||
        operationRef.current.executionId !== executionId
      ) {
        return;
      }
      showToast({
        id: "response-cancel",
        message: "応答を停止できませんでした。もう一度お試しください。",
        tone: "error",
      });
    } finally {
      if (
        mountedRef.current &&
        operationRef.current.kind === "cancelling" &&
        operationRef.current.executionId === executionId
      ) {
        setOperation(IDLE_RESPONSE_OPERATION);
      }
    }
  }

  function stopResponse() {
    const current = threadRef.current?.latest_response;
    const executionId =
      current && (current.status === "queued" || current.status === "running")
        ? current.execution.id
        : undefined;
    const next = requestResponseCancellation(operationRef.current, executionId);
    if (next === operationRef.current) return;
    setOperation(next);
    if (next.kind === "cancelling") void cancelResponse(next.executionId);
  }

  useEffect(() => {
    targetEntryIdRef.current = targetEntryId;
  }, [targetEntryId]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      dismissToast("message-send");
    };
  }, [dismissToast]);

  useEffect(() => {
    let cancelled = false;
    let humanDeliveryTimer: ReturnType<typeof setTimeout> | undefined;
    let humanDeliveryGeneration = 0;
    let presentedExecutionId: string | undefined;
    let presentedRevision: number | undefined;
    const humanAnswererIds = new Set(
      answerers
        .filter((option) => option.kind === "human")
        .map((option) => option.id),
    );

    async function syncThread(showLoading: boolean) {
      if (cancelled) return;
      const generation = ++refreshGenerationRef.current;
      if (showLoading) setLoading(true);
      try {
        const current = await loadThread();
        if (cancelled || generation !== refreshGenerationRef.current) return;
        setTurnAnchor((currentAnchor) => {
          if (targetEntryIdRef.current) return undefined;
          const activeEntryId = isResponding(current)
            ? current.latest_response?.input_entry_id
            : undefined;
          if (
            activeEntryId &&
            (currentAnchor?.threadId !== threadId ||
              currentAnchor.entryId !== activeEntryId)
          ) {
            return { entryId: activeEntryId, threadId };
          }
          if (currentAnchor?.threadId === threadId) return currentAnchor;
          return undefined;
        });
        updateThread((previous) =>
          previous?.id === current.id && previous.revision > current.revision
            ? previous
            : {
                ...current,
                entries:
                  previous?.id === current.id
                    ? mergeEntries(previous.entries, current.entries)
                    : current.entries,
              },
        );
        if (!answererInitializedRef.current) {
          answererInitializedRef.current = true;
          setAnswerer(current.answerer);
        }
        dismissToast("thread-load");
      } catch {
        if (cancelled || generation !== refreshGenerationRef.current) return;
        showToast({
          id: "thread-load",
          message: "会話を読み込めませんでした。",
          tone: "error",
          duration: null,
          action: {
            label: "再試行",
            onClick: () => void syncThread(true),
          },
        });
      } finally {
        if (!cancelled && generation === refreshGenerationRef.current) {
          setLoading(false);
        }
      }
    }

    function syncExecutionOnce(executionId: string | null) {
      const key = executionId ?? "thread";
      if (pendingExecutionSyncRef.current === key) {
        executionSyncDirtyRef.current = true;
        return;
      }
      pendingExecutionSyncRef.current = key;
      void syncThread(false).finally(() => {
        if (pendingExecutionSyncRef.current === key) {
          pendingExecutionSyncRef.current = undefined;
          if (executionSyncDirtyRef.current) {
            executionSyncDirtyRef.current = false;
            syncExecutionOnce(executionId);
          }
        }
      });
    }

    function applyResponseEvent(event: RealtimeEvent, sync = true) {
      const decision = reduceThreadRealtime(threadRef.current, event);
      if (!decision.handled) return;
      if (decision.next !== threadRef.current) {
        updateThread(() => decision.next);
      }
      if (
        event.type === "response.completed" ||
        event.type === "response.failed" ||
        event.type === "response.cancelled"
      ) {
        const nextOperation = resolveTerminalExecution(
          operationRef.current,
          event.execution_id,
        );
        if (nextOperation !== operationRef.current) setOperation(nextOperation);
      }
      if (decision.shouldSync && sync) syncExecutionOnce(event.execution_id);
    }

    function cancelHumanDelivery() {
      humanDeliveryGeneration += 1;
      if (humanDeliveryTimer) clearTimeout(humanDeliveryTimer);
      humanDeliveryTimer = undefined;
      presentedExecutionId = undefined;
      presentedRevision = undefined;
      setHumanResponsePresentation(undefined);
    }

    function flushHumanDelivery() {
      if (!presentedExecutionId) return false;
      cancelHumanDelivery();
      return true;
    }

    function startHumanDelivery(event: RealtimeEvent) {
      const content = event.data.content;
      applyResponseEvent(event);
      if (!content) {
        return;
      }
      const plan = createHumanResponseDeliveryPlan(content);
      if (plan.frames.length < 2) {
        return;
      }

      cancelHumanDelivery();
      const generation = humanDeliveryGeneration;
      if (!event.execution_id) return;
      presentedExecutionId = event.execution_id;
      presentedRevision = event.thread_revision;
      let frameIndex = 0;

      function revealNextFrame() {
        if (cancelled || generation !== humanDeliveryGeneration) return;
        if (document.visibilityState === "hidden") {
          flushHumanDelivery();
          return;
        }
        const frame = plan.frames[frameIndex];
        if (frame === undefined) {
          cancelHumanDelivery();
          return;
        }
        setHumanResponsePresentation({
          content: frame,
          executionId: event.execution_id!,
        });
        frameIndex += 1;
        if (frameIndex >= plan.frames.length) {
          cancelHumanDelivery();
          return;
        }
        humanDeliveryTimer = setTimeout(revealNextFrame, plan.intervalMs);
      }

      revealNextFrame();
    }

    function applyRealtime(event: RealtimeEvent) {
      if (event.type === "sync.required") {
        flushHumanDelivery();
        void syncThread(false);
        return;
      }
      if (event.thread_id !== threadId) return;
      if (
        presentedRevision !== undefined &&
        event.thread_revision > presentedRevision
      ) {
        flushHumanDelivery();
      }
      if (event.type === "entry.created") {
        void syncThread(false);
        return;
      }
      if (event.type === "thread.updated" && event.data.title) {
        updateThread((current) =>
          current && event.thread_revision >= current.revision
            ? {
                ...current,
                title: event.data.title ?? current.title,
                revision: event.thread_revision,
              }
            : current,
        );
        return;
      }
      if (
        isLiveHumanResponseCompletion(
          threadRef.current,
          event,
          humanAnswererIds,
        ) &&
        document.visibilityState !== "hidden" &&
        !window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ) {
        startHumanDelivery(event);
        return;
      }
      if (
        presentedExecutionId &&
        event.execution_id === presentedExecutionId
      ) {
        cancelHumanDelivery();
      }
      applyResponseEvent(event);
    }

    function handleVisibilityChange() {
      if (document.visibilityState === "hidden") flushHumanDelivery();
    }

    const unsubscribeRealtime = subscribeRealtime(applyRealtime);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    void syncThread(false);
    return () => {
      cancelHumanDelivery();
      cancelled = true;
      refreshGenerationRef.current += 1;
      pendingExecutionSyncRef.current = undefined;
      executionSyncDirtyRef.current = false;
      unsubscribeRealtime();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      dismissToast("thread-load");
    };
  }, [
    answerers,
    dismissToast,
    loadThread,
    realtimeReadyRevision,
    showToast,
    subscribeRealtime,
    threadId,
    updateThread,
  ]);

  useLayoutEffect(() => {
    if (
      !turnAnchorEntryId ||
      !thread?.entries.some((entry) => entry.id === turnAnchorEntryId)
    ) {
      return;
    }
    const turnKey = `${threadId}:${turnAnchorEntryId}`;
    if (positionedTurnRef.current === turnKey) return;
    if (anchorTurn()) positionedTurnRef.current = turnKey;
  }, [anchorTurn, thread, threadId, turnAnchorEntryId]);

  useEffect(() => {
    if (!targetEntryId) {
      scrolledTargetRef.current = undefined;
      return;
    }
    if (loading || !thread?.entries.some((entry) => entry.id === targetEntryId)) {
      return;
    }
    const targetKey = `${threadId}:${targetEntryId}:${activeSearchTarget?.sequence ?? "direct"}`;
    if (scrolledTargetRef.current === targetKey) return;

    const frame = requestAnimationFrame(() => {
      const element = document.getElementById(`thread-entry-${targetEntryId}`);
      if (!element) return;
      scrolledTargetRef.current = targetKey;
      const highlightedMatch = element.querySelector<HTMLElement>(
        "[data-search-highlight-target]",
      );
      setTurnAnchor(undefined);
      positionedTurnRef.current = undefined;
      scrollToEntry(element, highlightedMatch ?? element);
    });
    return () => cancelAnimationFrame(frame);
  }, [
    activeSearchTarget?.sequence,
    loading,
    scrollToEntry,
    targetEntryId,
    targetSearchQuery,
    thread,
    threadId,
  ]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const input = message.trim();
    if (!input || !answerer || responding) return;
    setTurnAnchor(undefined);
    positionedTurnRef.current = undefined;
    pinToBottom();
    setMessage("");
    setOperation({ kind: "creating" });
    settleComposerFocus(inputRef.current);
    dismissToast("message-send");
    try {
      const created = await createResponse(threadId, input, answerer);
      if (!mountedRef.current) return;
      updateThread((current) => {
        const entries = current
          ? mergeEntries(current.entries, created.thread.entries)
          : created.thread.entries;
        if (current && current.revision > created.thread.revision) {
          return {
            ...current,
            entries,
            latest_response:
              current.latest_response?.id === created.response.id
                ? current.latest_response
                : created.response,
          };
        }
        return { ...created.thread, entries, latest_response: created.response };
      });
      setTurnAnchor({
        entryId: created.response.input_entry_id,
        threadId,
      });
      const nextOperation = resolveCreatedExecution(
        operationRef.current,
        created.response.execution.id,
      );
      setOperation(nextOperation);
      patchThread(threadId, {
        answerer,
        last_activity_at: created.thread.last_activity_at,
        revision: created.thread.revision,
      });
      if (nextOperation.kind === "cancelling") {
        await cancelResponse(nextOperation.executionId);
      }
    } catch (error) {
      if (!mountedRef.current) return;
      setMessage((current) => (current.trim() ? current : input));
      setOperation(IDLE_RESPONSE_OPERATION);
      const insufficientCredits = isApiErrorStatus(error, 402);
      showToast({
        id: "message-send",
        message: insufficientCredits
          ? INSUFFICIENT_CREDITS_MESSAGE
          : "送信できませんでした。もう一度お試しください。",
        tone: insufficientCredits ? "warning" : "error",
      });
    }
  }

  return (
    <div
      ref={containerRef}
      className="flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain [overflow-anchor:none]"
      onKeyDown={handleScrollKeyDown}
      onPointerDown={handleScrollPointerDown}
      onScroll={handleScroll}
      onTouchMove={handleUserScrollIntent}
      onWheel={handleUserScrollIntent}
    >
      <ChatHeader
        answerer={answerer}
        answerers={answerers}
        onAnswererChange={selectAnswerer}
      />

      {humanPrivacyDialogOpen ? (
        <HumanPrivacyDialog onClose={() => setHumanPrivacyDialogOpen(false)} />
      ) : null}

      <div className="relative isolate flex flex-1 flex-col">
        <ResponseAmbient active={responding} />

        <ThreadViewport
          answerers={answerers}
          messageListRef={messageListRef}
          thread={thread}
          loading={loading}
          responding={responding}
          humanResponse={respondingAnswerer?.kind === "human"}
          humanResponsePresentation={humanResponsePresentation}
          turnAnchorEntryId={turnAnchorEntryId}
          turnAnchorRef={turnAnchorRef}
          turnSpacerRef={turnSpacerRef}
          targetEntryId={targetEntryId}
          targetSearchQuery={targetSearchQuery}
        />

        <div
          ref={footerRef}
          className="thread-composer sticky bottom-0 z-20 shrink-0 px-5 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-8"
        >
          <button
            type="button"
            aria-label="会話の最下部へ移動"
            aria-hidden={!showScrollToBottom}
            tabIndex={showScrollToBottom ? 0 : -1}
            className={`absolute -top-12 left-1/2 z-20 grid size-9 -translate-x-1/2 place-items-center rounded-full border border-[var(--divider)] bg-[var(--surface-translucent)] text-[var(--muted)] shadow-[0_8px_24px_var(--popover-shadow)] backdrop-blur-xl transition-[opacity,translate,background-color,color] hover:bg-[var(--hover)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] ${
              showScrollToBottom
                ? "translate-y-0 opacity-100"
                : "pointer-events-none translate-y-1 opacity-0"
            }`}
            onClick={scrollToBottom}
          >
            <ArrowDown aria-hidden="true" className="size-4" strokeWidth={2} />
          </button>
          <MessageComposer
            action={
              responding
                ? {
                    kind: "stop",
                    onStop: stopResponse,
                    pending: responseOperationIsPending(operation),
                  }
                : {
                    kind: "send",
                    disabled: !message.trim() || !answerer,
                  }
            }
            autoFocus
            className="relative z-10 mx-auto max-w-[760px]"
            inputId="thread-message"
            inputLabel="対話を続ける"
            onBlur={handleComposerBlur}
            onChange={(value) => {
              handleComposerInteraction();
              setMessage(value);
            }}
            onFocus={handleComposerInteraction}
            onSubmit={submit}
            placeholder="対話を続ける"
            sendShortcut={shortcuts.messageSend}
            textareaRef={inputRef}
            value={message}
          />
          <p className="relative z-10 mx-auto mt-2 max-w-[760px] text-center text-xs text-[var(--muted)]">
            {selectedAnswerer?.kind === "human"
              ? "Humanは考え、迷い、ときに間違えます。"
              : "SodAIは息をするように嘘をつきます。安易に信用しないでください。"}
          </p>
        </div>
      </div>
    </div>
  );
}
