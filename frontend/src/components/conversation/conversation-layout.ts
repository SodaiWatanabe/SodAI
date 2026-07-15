import type { Actor } from "@/lib/chat/types";

export type ConversationMessageLayout = {
  side: "left" | "right";
  surface: "bubble" | "generated";
};

export type ConversationPerspective = "answerer" | "prompter";

export function getConversationMessageLayout(
  authorKind: Actor["kind"],
  perspective: ConversationPerspective,
): ConversationMessageLayout {
  const isPrompterMessage = authorKind === "human";

  if (perspective === "answerer") {
    return isPrompterMessage
      ? { side: "left", surface: "bubble" }
      : { side: "left", surface: "generated" };
  }

  return isPrompterMessage
    ? { side: "right", surface: "bubble" }
    : { side: "left", surface: "generated" };
}
