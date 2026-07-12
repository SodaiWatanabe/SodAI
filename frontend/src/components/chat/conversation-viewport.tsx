"use client";

import type { RefObject } from "react";

import { IOSSpinner } from "@/components/ui/ios-spinner";
import type { ChatMessage, Conversation } from "@/lib/chat/types";

type ConversationViewportProps = {
  conversation?: Conversation;
  loading: boolean;
  scrollRef: RefObject<HTMLDivElement | null>;
};

function ConversationMessage({ message }: { message: ChatMessage }) {
  return (
    <article
      className={message.speaker === "partner" ? "flex justify-end" : "flex justify-start"}
    >
      <div
        className={
          message.speaker === "partner"
            ? "max-w-[82%] rounded-[22px] bg-[var(--field)] px-4 py-2.5 text-[15px] leading-6 text-[var(--text)]"
            : "max-w-[92%] whitespace-pre-wrap text-[15px] leading-7 text-[var(--text)]"
        }
      >
        {message.content}
        {message.speaker === "sodai" && message.status === "streaming" ? (
          <span className="ml-1 inline-block size-1.5 animate-pulse rounded-full bg-[var(--muted)] align-middle" />
        ) : null}
        {message.status === "failed" ? (
          <span className="text-sm text-[var(--danger-text)]">
            応答を完了できませんでした。
          </span>
        ) : null}
      </div>
    </article>
  );
}

export function ConversationViewport({
  conversation,
  loading,
  scrollRef,
}: ConversationViewportProps) {
  return (
    <section
      aria-label="会話"
      aria-busy={loading}
      className="relative min-h-0 flex-1"
    >
      <div
        ref={scrollRef}
        className="absolute inset-0 overflow-y-auto scroll-smooth"
      >
        {conversation ? (
          <div className="mx-auto w-full max-w-[760px] px-5 py-10 sm:px-8">
            <div className="space-y-8">
              {conversation.messages.map((message) => (
                <ConversationMessage key={message.id} message={message} />
              ))}
            </div>
          </div>
        ) : !loading ? (
          <div className="grid h-full place-items-center px-5 text-sm text-[var(--muted)]">
            この会話を表示できません。
          </div>
        ) : null}
      </div>

      {loading ? (
        <div className="absolute inset-0 z-10 grid place-items-center bg-[var(--canvas)] text-[var(--muted)]">
          <IOSSpinner label="会話を読み込み中" />
        </div>
      ) : null}
    </section>
  );
}
