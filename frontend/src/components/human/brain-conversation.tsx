import type { ReactNode, Ref } from "react";

import { getConversationMessageLayout } from "@/components/conversation/conversation-layout";
import { ConversationMessage } from "@/components/conversation/conversation-message";
import type { HumanContextEntry } from "@/lib/human/types";

export function BrainConversation({
  children,
  context,
  turnAnchorRef,
}: {
  children: ReactNode;
  context: HumanContextEntry[];
  turnAnchorRef?: Ref<HTMLElement>;
}) {
  const turnAnchorIndex = context.reduce(
    (latestIndex, entry, index) =>
      entry.author_kind === "human" ? index : latestIndex,
    -1,
  );

  return (
    <div className="space-y-8">
      {context.map((entry, index) => (
        <ConversationMessage
          key={index}
          {...getConversationMessageLayout(entry.author_kind, "answerer")}
          articleRef={index === turnAnchorIndex ? turnAnchorRef : undefined}
          turnAnchor={index === turnAnchorIndex}
        >
          {entry.content}
        </ConversationMessage>
      ))}
      {children}
    </div>
  );
}
