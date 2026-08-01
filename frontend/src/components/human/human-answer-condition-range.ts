import type { ReasoningEffort } from "@/lib/chat/types";

export const HUMAN_REASONING_EFFORT_ORDER: readonly ReasoningEffort[] = [
  "low",
  "medium",
  "high",
  "xhigh",
];

export type DiscreteRange = {
  lower: number;
  upper: number;
};

export function rangeIndices<T>(
  options: readonly T[],
  selected: readonly T[],
): DiscreteRange {
  const indices = selected
    .map((item) => options.indexOf(item))
    .filter((index) => index >= 0);
  if (indices.length === 0) return { lower: 0, upper: 0 };
  return {
    lower: Math.min(...indices),
    upper: Math.max(...indices),
  };
}

export function valuesInRange<T>(
  options: readonly T[],
  range: DiscreteRange,
): T[] {
  return options.slice(range.lower, range.upper + 1);
}

export function formatConditionRange(
  labels: readonly string[],
  range: DiscreteRange,
): string {
  const lower = labels[range.lower] ?? "";
  const upper = labels[range.upper] ?? lower;
  return range.lower === range.upper ? lower : `${lower}〜${upper}`;
}
