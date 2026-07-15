"use client";

import { type Ref, type RefObject } from "react";

import { SearchHighlight } from "@/components/chat/search-highlight";
import { MessageActions } from "@/components/chat/message-actions";
import { resolveMessageBrain } from "@/components/chat/message-brain";
import { getConversationMessageLayout } from "@/components/conversation/conversation-layout";
import { ConversationMessage } from "@/components/conversation/conversation-message";
import { IOSSpinner } from "@/components/ui/ios-spinner";
import type {
  AvailableAnswerer,
  Thread,
  ThreadEntry,
} from "@/lib/chat/types";

type ThreadViewportProps = {
  messageListRef: RefObject<HTMLDivElement | null>;
  thread?: Thread;
  loading: boolean;
  responding: boolean;
  humanResponse?: boolean;
  turnAnchorEntryId?: string;
  turnAnchorRef: Ref<HTMLElement>;
  turnSpacerRef: Ref<HTMLDivElement>;
  targetEntryId?: string;
  targetSearchQuery?: string;
  answerers: AvailableAnswerer[];
};

type DisplayEntry = ThreadEntry & {
  responseStatus: "completed" | "streaming" | "failed";
};

function StreamedText({ content }: { content: string }) {
  return <span className="stream-response-enter">{content}</span>;
}

function ThreadMessage({
  answerers,
  entry,
  entryRef,
  searchQuery,
  searchAnchor,
  turnAnchor,
}: {
  answerers: AvailableAnswerer[];
  entry: DisplayEntry;
  entryRef?: Ref<HTMLElement>;
  searchQuery?: string;
  searchAnchor: boolean;
  turnAnchor: boolean;
}) {
  const layout = getConversationMessageLayout(entry.author.kind, "prompter");
  const showActions =
    layout.surface === "generated" &&
    entry.responseStatus === "completed" &&
    entry.content.length > 0;
  return (
    <ConversationMessage
      articleRef={entryRef}
      id={`thread-entry-${entry.id}`}
      searchAnchor={searchAnchor}
      turnAnchor={turnAnchor}
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
      {showActions ? (
        <MessageActions
          brain={resolveMessageBrain(entry, answerers)}
          content={entry.content}
        />
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
    answerer: response.requested_answerer,
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
  answerers,
  messageListRef,
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
                key={entry.id}
                answerers={answerers}
                entry={entry}
                entryRef={
                  entry.id === turnAnchorEntryId ? turnAnchorRef : undefined
                }
                searchQuery={targetSearchQuery}
                searchAnchor={entry.id === targetEntryId}
                turnAnchor={entry.id === turnAnchorEntryId}
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
