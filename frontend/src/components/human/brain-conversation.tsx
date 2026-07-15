import type { ReactNode } from "react";

import { getConversationMessageLayout } from "@/components/conversation/conversation-layout";
import { ConversationMessage } from "@/components/conversation/conversation-message";
import type { HumanContextEntry } from "@/lib/human/types";

export function BrainConversation({
  children,
  context,
}: {
  children: ReactNode;
  context: HumanContextEntry[];
}) {
  return (
    <div className="space-y-8">
      {context.map((entry, index) => (
        <ConversationMessage
          key={index}
          {...getConversationMessageLayout(entry.author_kind, "answerer")}
        >
          {entry.content}
        </ConversationMessage>
      ))}
      {children}
    </div>
  );
}
