import type { ReactNode } from "react";

import type { ConversationMessageLayout } from "@/components/conversation/conversation-layout";

type ConversationMessageProps = ConversationMessageLayout & {
  children: ReactNode;
  id?: string;
  searchAnchor?: boolean;
};

export function ConversationMessage({
  children,
  id,
  searchAnchor = false,
  side,
  surface,
}: ConversationMessageProps) {
  return (
    <article
      id={id}
      tabIndex={searchAnchor ? -1 : undefined}
      className={`${side === "right" ? "justify-end" : "justify-start"} flex scroll-mt-24 outline-none`}
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
