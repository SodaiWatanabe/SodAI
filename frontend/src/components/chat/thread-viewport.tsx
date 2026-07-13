"use client";

import { useLayoutEffect, useRef, useState } from "react";

import { IOSSpinner } from "@/components/ui/ios-spinner";
import type { Thread, ThreadEntry } from "@/lib/chat/types";

type ThreadViewportProps = {
  thread?: Thread;
  loading: boolean;
  responding: boolean;
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

function ThreadMessage({ entry }: { entry: DisplayEntry }) {
  const isPartner = entry.author.kind === "human";
  return (
    <article className={isPartner ? "flex justify-end" : "flex justify-start"}>
      <div
        className={
          isPartner
            ? "max-w-[82%] rounded-[22px] rounded-br-md bg-[var(--field)] px-4 py-2.5 text-[15px] leading-6 text-[var(--text)]"
            : "max-w-[92%] whitespace-pre-wrap text-[15px] leading-7 text-[var(--text)]"
        }
      >
        {!isPartner && entry.responseStatus === "streaming" ? (
          <StreamedText content={entry.content} />
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
  thread,
  loading,
  responding,
}: ThreadViewportProps) {
  const entries = thread ? displayEntries(thread) : [];
  return (
    <section
      aria-label="会話"
      aria-busy={loading || responding}
      className="relative isolate flex flex-1 flex-col"
    >
      <div
        aria-hidden="true"
        data-active={responding ? "true" : "false"}
        className="response-ambient"
      >
        <span className="response-glow response-glow-one" />
        <span className="response-glow response-glow-two" />
        <span className="response-glow response-glow-three" />
      </div>
      {responding ? (
        <span role="status" className="sr-only">
          SodAIが応答しています
        </span>
      ) : null}

      {thread ? (
        <div className="relative z-10 mx-auto w-full max-w-[760px] px-5 pb-12 pt-10 sm:px-8">
          <div className="space-y-8">
            {entries.map((entry) => (
              <ThreadMessage key={entry.id} entry={entry} />
            ))}
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
