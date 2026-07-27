import type { RealtimeEvent, Thread } from "@/lib/chat/types";

const MIN_DELIVERY_DURATION_MS = 420;
const MAX_DELIVERY_DURATION_MS = 2_200;
const DELIVERY_MS_PER_GRAPHEME = 22;
const TARGET_FRAME_INTERVAL_MS = 48;
const MAX_DELIVERY_FRAMES = 40;

type HumanResponseDeliveryPlan = {
  frames: string[];
  intervalMs: number;
};

const graphemeSegmenter =
  typeof Intl.Segmenter === "function"
    ? new Intl.Segmenter(undefined, { granularity: "grapheme" })
    : undefined;

function splitGraphemes(content: string) {
  if (!graphemeSegmenter) return Array.from(content);
  return Array.from(
    graphemeSegmenter.segment(content),
    ({ segment }) => segment,
  );
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(Math.max(value, minimum), maximum);
}

export function createHumanResponseDeliveryPlan(
  content: string,
): HumanResponseDeliveryPlan {
  const graphemes = splitGraphemes(content);
  if (graphemes.length === 0) return { frames: [], intervalMs: 0 };

  const durationMs = clamp(
    graphemes.length * DELIVERY_MS_PER_GRAPHEME,
    MIN_DELIVERY_DURATION_MS,
    MAX_DELIVERY_DURATION_MS,
  );
  const frameCount = Math.min(
    graphemes.length,
    MAX_DELIVERY_FRAMES,
    Math.max(1, Math.round(durationMs / TARGET_FRAME_INTERVAL_MS)),
  );
  const frames = Array.from({ length: frameCount }, (_, index) => {
    const end = Math.ceil(((index + 1) * graphemes.length) / frameCount);
    return graphemes.slice(0, end).join("");
  });

  return {
    frames,
    intervalMs:
      frameCount > 1 ? Math.round(durationMs / (frameCount - 1)) : 0,
  };
}

export function isLiveHumanResponseCompletion(
  current: Thread | undefined,
  event: RealtimeEvent,
  humanAnswererIds: ReadonlySet<string>,
) {
  if (event.type !== "response.completed" || !event.data.content) return false;
  const response = current?.latest_response;
  if (
    !response ||
    (response.status !== "queued" && response.status !== "running")
  ) {
    return false;
  }
  return (
    response.id === event.response_request_id &&
    response.execution.id === event.execution_id &&
    humanAnswererIds.has(response.requested_answerer)
  );
}
