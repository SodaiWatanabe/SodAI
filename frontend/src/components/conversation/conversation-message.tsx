import type { ReactNode, Ref } from "react";

import type { ConversationMessageLayout } from "@/components/conversation/conversation-layout";

type ConversationMessageProps = ConversationMessageLayout & {
  articleRef?: Ref<HTMLElement>;
  children: ReactNode;
  id?: string;
  searchAnchor?: boolean;
  turnAnchor?: boolean;
};

export function ConversationMessage({
  articleRef,
  children,
  id,
  searchAnchor = false,
  side,
  surface,
  turnAnchor = false,
}: ConversationMessageProps) {
  return (
    <article
      ref={articleRef}
      id={id}
      tabIndex={searchAnchor ? -1 : undefined}
      className={`${side === "right" ? "justify-end" : "justify-start"} flex outline-none ${turnAnchor ? "scroll-mt-16" : "scroll-mt-24"}`}
    >
      <div
        className={
          surface === "bubble"
            ? `max-w-[82%] whitespace-pre-wrap rounded-[22px] bg-[var(--field)] px-4 py-2.5 text-[15px] leading-6 text-[var(--text)] ${
                side === "right" ? "rounded-br-md" : "rounded-tl-md"
              }`
            : "w-full whitespace-pre-wrap text-[15px] leading-7 text-[var(--text)]"
        }
      >
        {children}
      </div>
    </article>
  );
}
