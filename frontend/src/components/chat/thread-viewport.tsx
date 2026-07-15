"use client";

import {
  type Ref,
  type RefObject,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

import { SearchHighlight } from "@/components/chat/search-highlight";
import { getConversationMessageLayout } from "@/components/conversation/conversation-layout";
import { ConversationMessage } from "@/components/conversation/conversation-message";
import { IOSSpinner } from "@/components/ui/ios-spinner";
import type { Thread, ThreadEntry } from "@/lib/chat/types";

type ThreadViewportProps = {
  contentRef: RefObject<HTMLDivElement | null>;
  thread?: Thread;
  loading: boolean;
  responding: boolean;
  humanResponse?: boolean;
  turnAnchorEntryId?: string;
  turnAnchorRef: Ref<HTMLElement>;
  turnSpacerRef: Ref<HTMLDivElement>;
  targetEntryId?: string;
  targetSearchQuery?: string;
};

type StreamSegment = {
  entering: boolean;
  key: number;
  text: string;
};

type DisplayEntry = ThreadEntry & {
  responseStatus: "completed" | "streaming" | "failed";
};

function StreamedText({ content }: { content: string }) {
  const previousContentRef = useRef(content);
  const sequenceRef = useRef(0);
  const [segments, setSegments] = useState<StreamSegment[]>([
    { entering: false, key: 0, text: content },
  ]);

  useLayoutEffect(() => {
    const previousContent = previousContentRef.current;
    if (content === previousContent) return;
    previousContentRef.current = content;
    sequenceRef.current += 1;

    if (content.startsWith(previousContent)) {
      setSegments((current) => [
        ...current,
        {
          entering: true,
          key: sequenceRef.current,
          text: content.slice(previousContent.length),
        },
      ]);
      return;
    }

    setSegments([{ entering: false, key: sequenceRef.current, text: content }]);
  }, [content]);

  function settleSegment(key: number) {
    setSegments((current) => {
      const settledIndex = current.findIndex((segment) => segment.key === key);
      if (settledIndex < 0) return current;
      return [
        {
          entering: false,
          key,
          text: current
            .slice(0, settledIndex + 1)
            .map((segment) => segment.text)
            .join(""),
        },
        ...current.slice(settledIndex + 1),
      ];
    });
  }

  return (
    <>
      {segments.map((segment) =>
        segment.entering ? (
          <span
            key={segment.key}
            className="stream-token-enter"
            onAnimationEnd={() => settleSegment(segment.key)}
          >
            {segment.text}
          </span>
        ) : (
          <span key={segment.key}>{segment.text}</span>
        ),
      )}
    </>
  );
}

function ThreadMessage({
  entry,
  entryRef,
  searchQuery,
  searchAnchor,
}: {
  entry: DisplayEntry;
  entryRef?: Ref<HTMLElement>;
  searchQuery?: string;
  searchAnchor: boolean;
}) {
  const layout = getConversationMessageLayout(entry.author.kind, "prompter");
  return (
    <ConversationMessage
      articleRef={entryRef}
      id={`thread-entry-${entry.id}`}
      searchAnchor={searchAnchor}
      {...layout}
    >
      {layout.surface === "generated" &&
      entry.responseStatus === "streaming" ? (
        <StreamedText content={entry.content} />
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
    </ConversationMessage>
  );
}

function displayEntries(thread: Thread): DisplayEntry[] {
  const entries: DisplayEntry[] = thread.entries.map((entry) => ({
    ...entry,
    responseStatus: "completed",
  }));
  const response = thread.latest_response;
  if (!response) return entries;
  const resultIsPersisted = response.execution.result_entry_id
    ? entries.some((entry) => entry.id === response.execution.result_entry_id)
    : false;
  if (response.status === "completed" && resultIsPersisted) return entries;
  const latestOrdinal = entries.at(-1)?.ordinal ?? -1;
  entries.push({
    id: response.execution.result_entry_id ?? `execution:${response.execution.id}`,
    thread_id: thread.id,
    author: response.target_actor,
    kind: "message",
    content: response.execution.partial_output,
    ordinal: latestOrdinal + 1,
    created_at: response.created_at,
    responseStatus:
      response.status === "failed"
        ? "failed"
        : response.status === "completed"
          ? "completed"
          : "streaming",
  });
  return entries;
}

export function ThreadViewport({
  contentRef,
  thread,
  loading,
  responding,
  humanResponse = false,
  turnAnchorEntryId,
  turnAnchorRef,
  turnSpacerRef,
  targetEntryId,
  targetSearchQuery,
}: ThreadViewportProps) {
  const entries = thread ? displayEntries(thread) : [];
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
          ref={contentRef}
          className="relative z-10 mx-auto w-full max-w-[760px] px-5 pb-12 pt-10 sm:px-8"
        >
          <div className="space-y-8">
            {visibleEntries.map((entry) => (
              <ThreadMessage
                key={entry.id}
                entry={entry}
                entryRef={
                  entry.id === turnAnchorEntryId ? turnAnchorRef : undefined
                }
                searchQuery={targetSearchQuery}
                searchAnchor={entry.id === targetEntryId}
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
