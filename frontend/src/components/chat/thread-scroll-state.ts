export type ThreadScrollMode = "bottom" | "turn" | "detached";

export type ThreadScrollEvent =
  | "anchor-turn"
  | "detach"
  | "pin-bottom";

export type TurnScrollMetrics = {
  containerHeight: number;
  containerScrollTop: number;
  containerTop: number;
  entryTop: number;
  scrollHeight: number;
  scrollMarginTop: number;
  spacerHeight: number;
};

export type TurnScrollLayout = {
  scrollTop: number;
  spacerHeight: number;
};

export type ScrollPositionMetrics = {
  containerHeight: number;
  scrollHeight: number;
  scrollTop: number;
};

export function transitionThreadScrollMode(
  current: ThreadScrollMode,
  event: ThreadScrollEvent,
): ThreadScrollMode {
  switch (event) {
    case "anchor-turn":
      return "turn";
    case "detach":
      return "detached";
    case "pin-bottom":
      return "bottom";
    default:
      return current;
  }
}

export function calculateTurnScrollLayout(
  metrics: TurnScrollMetrics,
): TurnScrollLayout {
  const scrollTop = Math.max(
    0,
    metrics.containerScrollTop +
      metrics.entryTop -
      metrics.containerTop -
      metrics.scrollMarginTop,
  );
  const contentHeightWithoutSpacer = Math.max(
    0,
    metrics.scrollHeight - metrics.spacerHeight,
  );
  const spacerHeight = Math.max(
    0,
    scrollTop + metrics.containerHeight - contentHeightWithoutSpacer,
  );

  return {
    scrollTop,
    spacerHeight,
  };
}

export function isScrollNearBottom(
  metrics: ScrollPositionMetrics,
  threshold: number,
) {
  const distance =
    metrics.scrollHeight - metrics.scrollTop - metrics.containerHeight;
  return distance <= threshold;
}

export function shouldShowScrollToBottom(
  mode: ThreadScrollMode,
  metrics: ScrollPositionMetrics,
  threshold: number,
) {
  return mode === "detached" && !isScrollNearBottom(metrics, threshold);
}

export function resolveScrollToBottomMode(
  turnSpacerHeight: number,
  tolerance: number,
): Extract<ThreadScrollMode, "bottom" | "turn"> {
  return turnSpacerHeight > tolerance ? "turn" : "bottom";
}
