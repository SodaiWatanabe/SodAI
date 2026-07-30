import type {
  AvailableAnswerer,
  ReasoningEffort,
} from "@/lib/chat/types";

export function resolveReasoningEffort(
  answerer: AvailableAnswerer | undefined,
  requested: ReasoningEffort | undefined,
): ReasoningEffort | undefined {
  if (!answerer) return undefined;
  if (
    requested &&
    answerer.reasoning_efforts.some((option) => option.id === requested)
  ) {
    return requested;
  }
  return answerer.default_reasoning_effort;
}

export function formatReasoningTimeLimit(seconds: number | null): string {
  if (seconds === null) return "時間制限なし";
  const hours = seconds / 3600;
  if (Number.isInteger(hours)) return `最大${hours}時間`;
  const minutes = seconds / 60;
  return Number.isInteger(minutes)
    ? `最大${minutes}分間`
    : `最大${seconds}秒間`;
}

export function reasoningEffortName(effort: ReasoningEffort): string {
  return {
    none: "なし",
    low: "軽い",
    medium: "中程度",
    high: "深い",
    xhigh: "非常に深い",
  }[effort];
}
