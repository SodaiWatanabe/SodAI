"use client";

import { type Ref, type RefObject, useEffect, useRef, useState } from "react";

import { SearchHighlight } from "@/components/chat/search-highlight";
import { MessageActions } from "@/components/chat/message-actions";
import { resolveMessageBrain } from "@/components/chat/message-brain";
import {
  appendStreamedText,
  createStreamedTextState,
  settleStreamedText,
  STREAM_RESPONSE_FADE_DURATION_MS,
} from "@/components/chat/streamed-text-state";
import {
  displayThreadEntries,
  type DisplayEntry,
  type ResponsePresentation,
} from "@/components/chat/thread-display-entries";
import { getConversationMessageLayout } from "@/components/conversation/conversation-layout";
import { ConversationMessage } from "@/components/conversation/conversation-message";
import { IOSSpinner } from "@/components/ui/ios-spinner";
import type {
  AvailableAnswerer,
  ResponseEvaluationValue,
  Thread,
} from "@/lib/chat/types";

type ThreadViewportProps = {
  messageListRef: RefObject<HTMLDivElement | null>;
  thread?: Thread;
  loading: boolean;
  responding: boolean;
  humanResponse?: boolean;
  humanResponsePresentation?: ResponsePresentation;
  turnAnchorEntryId?: string;
  turnAnchorRef: Ref<HTMLElement>;
  turnSpacerRef: Ref<HTMLDivElement>;
  targetEntryId?: string;
  targetSearchQuery?: string;
  answerers: AvailableAnswerer[];
  onEvaluationChange: (
    executionId: string,
    value: ResponseEvaluationValue | null,
  ) => Promise<void>;
};

function StreamedText({
  content,
  markFirstMatch,
  searchQuery,
  streaming,
}: {
  content: string;
  markFirstMatch: boolean;
  searchQuery?: string;
  streaming: boolean;
}) {
  const latestContentRef = useRef(content);
  const frameRef = useRef<number | undefined>(undefined);
  const settledThroughRef = useRef<number | undefined>(undefined);
  const [stream, setStream] = useState(() =>
    createStreamedTextState(content, streaming),
  );

  useEffect(() => {
    if (latestContentRef.current === content) return;
    latestContentRef.current = content;
    if (frameRef.current !== undefined) return;
    frameRef.current = window.requestAnimationFrame(() => {
      frameRef.current = undefined;
      setStream((current) =>
        appendStreamedText(
          current,
          latestContentRef.current,
          settledThroughRef.current,
        ),
      );
    });
  }, [content]);

  useEffect(
    () => () => {
      if (frameRef.current !== undefined) {
        window.cancelAnimationFrame(frameRef.current);
      }
    },
    [],
  );

  useEffect(() => {
    if (streaming || !stream.animated || stream.content !== content) return;
    const timer = window.setTimeout(() => {
      setStream((current) =>
        current.content === content ? settleStreamedText(current) : current,
      );
    }, STREAM_RESPONSE_FADE_DURATION_MS);
    return () => window.clearTimeout(timer);
  }, [content, stream.animated, stream.content, streaming]);

  function markSegmentSettled(key: number) {
    settledThroughRef.current = Math.max(
      settledThroughRef.current ?? key,
      key,
    );
  }

  if (!stream.animated && searchQuery) {
    return (
      <SearchHighlight
        markFirstMatch={markFirstMatch}
        query={searchQuery}
        text={stream.content}
      />
    );
  }

  return (
    <>
      {stream.segments.map((segment) => (
        <span
          key={segment.key}
          className={segment.entering ? "stream-response-enter" : undefined}
          onAnimationEnd={
            segment.entering
              ? () => markSegmentSettled(segment.key)
              : undefined
          }
        >
          {segment.text}
        </span>
      ))}
    </>
  );
}

function ThreadMessage({
  answerers,
  entry,
  entryRef,
  searchQuery,
  searchAnchor,
  turnAnchor,
  onEvaluationChange,
}: {
  answerers: AvailableAnswerer[];
  entry: DisplayEntry;
  entryRef?: Ref<HTMLElement>;
  searchQuery?: string;
  searchAnchor: boolean;
  turnAnchor: boolean;
  onEvaluationChange: (
    executionId: string,
    value: ResponseEvaluationValue | null,
  ) => Promise<void>;
}) {
  const layout = getConversationMessageLayout(entry.author.kind, "prompter");
  const showActions =
    layout.surface === "generated" &&
    (entry.responseStatus === "completed" ||
      entry.responseStatus === "cancelled") &&
    !entry.presenting &&
    entry.content.length > 0;
  const evaluationExecutionId =
    entry.responseStatus === "completed" ? entry.execution_id : null;
  return (
    <ConversationMessage
      articleRef={entryRef}
      id={`thread-entry-${entry.id}`}
      searchAnchor={searchAnchor}
      turnAnchor={turnAnchor}
      {...layout}
    >
      {layout.surface === "generated" ? (
        <StreamedText
          content={entry.content}
          markFirstMatch={searchAnchor}
          searchQuery={searchQuery}
          streaming={entry.responseStatus === "streaming" || entry.presenting}
        />
      ) : searchQuery ? (
        <SearchHighlight
          markFirstMatch={searchAnchor}
          query={searchQuery}
          text={entry.content}
        />
      ) : (
        entry.content
      )}
      {entry.responseStatus === "failed" ? (
        <span className="text-[var(--danger-text)]">
          応答を完了できませんでした。
        </span>
      ) : null}
      {entry.responseStatus === "cancelled" && !entry.presenting ? (
        <span className="mt-2 block text-[var(--muted)]">
          応答を停止しました。
        </span>
      ) : null}
      {showActions ? (
        <MessageActions
          brain={resolveMessageBrain(entry, answerers)}
          content={entry.content}
          evaluation={entry.evaluation}
          onEvaluationChange={
            evaluationExecutionId
              ? (value) => onEvaluationChange(evaluationExecutionId, value)
              : undefined
          }
        />
      ) : null}
    </ConversationMessage>
  );
}

export function ThreadViewport({
  answerers,
  messageListRef,
  thread,
  loading,
  responding,
  humanResponse = false,
  humanResponsePresentation,
  turnAnchorEntryId,
  turnAnchorRef,
  turnSpacerRef,
  targetEntryId,
  targetSearchQuery,
  onEvaluationChange,
}: ThreadViewportProps) {
  const entries = thread
    ? displayThreadEntries(thread, humanResponsePresentation)
    : [];
  const waitingForFirstToken =
    responding &&
    !entries.some(
      (entry) =>
        entry.responseStatus === "streaming" && entry.content.trim().length > 0,
    );
  const visibleEntries = waitingForFirstToken
    ? entries.filter(
        (entry) =>
          entry.responseStatus !== "streaming" ||
          entry.content.trim().length > 0,
      )
    : entries;
  const turnAnchorStartsThread =
    visibleEntries[0]?.id === turnAnchorEntryId;
  const searchingForHuman =
    humanResponse && thread?.latest_response?.status !== "running";
  const responseStatusText = humanResponse
    ? searchingForHuman
      ? "利用可能な脳を探しています"
      : "思考中"
    : "SodAIが応答しています";

  return (
    <section
      aria-label="会話"
      aria-busy={loading || responding}
      className="relative isolate flex flex-1 flex-col"
    >
      {responding ? (
        <span role="status" className="sr-only">
          {responseStatusText}
        </span>
      ) : null}

      {thread ? (
        <div
          className={`relative z-10 mx-auto w-full max-w-[760px] px-5 pb-12 sm:px-8 ${turnAnchorStartsThread ? "pt-4" : "pt-10"}`}
        >
          <div ref={messageListRef} className="space-y-8">
            {visibleEntries.map((entry) => (
              <ThreadMessage
                key={entry.renderKey}
                answerers={answerers}
                entry={entry}
                entryRef={
                  entry.id === turnAnchorEntryId ? turnAnchorRef : undefined
                }
                searchQuery={targetSearchQuery}
                searchAnchor={entry.id === targetEntryId}
                turnAnchor={entry.id === turnAnchorEntryId}
                onEvaluationChange={onEvaluationChange}
              />
            ))}
            {waitingForFirstToken ? (
              <article
                aria-hidden="true"
                className="flex h-7 items-center justify-start text-[15px] leading-7 text-[var(--muted)]"
              >
                {humanResponse ? (
                  <span className="human-search-status">
                    {responseStatusText}
                  </span>
                ) : (
                  <span className="response-waiting-dot" />
                )}
              </article>
            ) : null}
          </div>
          {turnAnchorEntryId &&
          visibleEntries.some((entry) => entry.id === turnAnchorEntryId) ? (
            <div
              ref={turnSpacerRef}
              aria-hidden="true"
              className="h-0 shrink-0"
            />
          ) : null}
        </div>
      ) : null}

      {loading ? (
        <div className="absolute inset-0 z-10 grid place-items-center bg-[var(--canvas)] text-[var(--muted)]">
          <IOSSpinner label="会話を読み込み中" />
        </div>
      ) : null}
    </section>
  );
}
