"use client";

import {
  type RefObject,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

import { SearchHighlight } from "@/components/chat/search-highlight";
import { IOSSpinner } from "@/components/ui/ios-spinner";
import type { Thread, ThreadEntry } from "@/lib/chat/types";

type ThreadViewportProps = {
  contentRef: RefObject<HTMLDivElement | null>;
  thread?: Thread;
  loading: boolean;
  responding: boolean;
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
  searchQuery,
  searchAnchor,
}: {
  entry: DisplayEntry;
  searchQuery?: string;
  searchAnchor: boolean;
}) {
  const isPartner = entry.author.kind === "human";
  return (
    <article
      id={`thread-entry-${entry.id}`}
      tabIndex={searchAnchor ? -1 : undefined}
      className={`${isPartner ? "flex justify-end" : "flex justify-start"} thread-message scroll-mt-24 rounded-2xl outline-none`}
    >
      <div
        className={
          isPartner
            ? "max-w-[82%] whitespace-pre-wrap rounded-[22px] rounded-br-md bg-[var(--field)] px-4 py-2.5 text-[15px] leading-6 text-[var(--text)]"
            : "max-w-[92%] whitespace-pre-wrap text-[15px] leading-7 text-[var(--text)]"
        }
      >
        {!isPartner && entry.responseStatus === "streaming" ? (
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
      </div>
    </article>
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

  return (
    <section
      aria-label="会話"
      aria-busy={loading || responding}
      className="relative isolate flex flex-1 flex-col"
    >
      {responding ? (
        <span role="status" className="sr-only">
          SodAIが応答しています
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
                searchQuery={targetSearchQuery}
                searchAnchor={entry.id === targetEntryId}
              />
            ))}
            {waitingForFirstToken ? (
              <article
                aria-hidden="true"
                className="flex h-7 items-center justify-start text-[15px]"
              >
                <span className="response-waiting-dot" />
              </article>
            ) : null}
          </div>
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
