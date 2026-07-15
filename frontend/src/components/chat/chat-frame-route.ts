export type SodaiProduct = "chat" | "brain";

export type ChatFrameRoute = {
  activeThreadId?: string;
  newChatActive: boolean;
  product: SodaiProduct;
};

/**
 * Resolves persistent frame state from the active children slot.
 *
 * Intercepted routes change the visible URL to `/settings`, while Next.js keeps
 * the previous page active in the children slot. Reading the URL here would
 * therefore discard whether the settings dialog was opened from Chat or Brain.
 */
export function resolveChatFrameRoute(
  childSegments: readonly string[],
): ChatFrameRoute {
  const rootSegment = childSegments.at(0);

  return {
    activeThreadId:
      rootSegment === "t" ? childSegments.at(1) : undefined,
    newChatActive: rootSegment === undefined,
    product: rootSegment === "brain" ? "brain" : "chat",
  };
}
