"use client";

import { useLayoutEffect, useRef, useState } from "react";

import { IOSSpinner } from "@/components/ui/ios-spinner";
import type { ChatMessage, Conversation } from "@/lib/chat/types";

type ConversationViewportProps = {
  conversation?: Conversation;
  loading: boolean;
  responding: boolean;
};

type StreamSegment = {
  entering: boolean;
  key: number;
  text: string;
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

    setSegments([
      { entering: false, key: sequenceRef.current, text: content },
    ]);
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

function ConversationMessage({ message }: { message: ChatMessage }) {
  return (
    <article
      className={message.speaker === "partner" ? "flex justify-end" : "flex justify-start"}
    >
      <div
        className={
          message.speaker === "partner"
            ? "max-w-[82%] rounded-[22px] rounded-br-md bg-[var(--field)] px-4 py-2.5 text-[15px] leading-6 text-[var(--text)]"
            : "max-w-[92%] whitespace-pre-wrap text-[15px] leading-7 text-[var(--text)]"
        }
      >
        {message.speaker === "sodai" ? (
          <StreamedText content={message.content} />
        ) : (
          message.content
        )}
        {message.status === "failed" ? (
          <span className="text-[var(--danger-text)]">
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
  responding,
}: ConversationViewportProps) {
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

      {conversation ? (
        <div className="relative z-10 mx-auto w-full max-w-[760px] px-5 pb-12 pt-10 sm:px-8">
          <div className="space-y-8">
            {conversation.messages.map((message) => (
              <ConversationMessage key={message.id} message={message} />
            ))}
          </div>
        </div>
      ) : !loading ? (
        <div className="grid flex-1 place-items-center px-5 text-sm text-[var(--muted)]">
          この会話を表示できません。
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
