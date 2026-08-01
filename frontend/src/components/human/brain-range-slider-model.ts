import type { DiscreteRange } from "@/components/human/human-answer-condition-range";

export const BRAIN_RANGE_THUMB_RADIUS_PX = 14;

export type RangeBoundaryLimits = {
  lowerMaximum: number;
  upperMaximum: number;
};

export type RangeBoundary = "lower" | "upper";

export type RangeBoundaryMove = {
  boundary: RangeBoundary;
  range: DiscreteRange;
};

export function rangePosition(
  index: number,
  maximum: number,
  thumbRadius = BRAIN_RANGE_THUMB_RADIUS_PX,
): string {
  const ratio = index / Math.max(1, maximum);
  const offset = thumbRadius * (1 - 2 * ratio);
  const operator = offset < 0 ? "-" : "+";
  return `calc(${ratio * 100}% ${operator} ${Math.abs(offset)}px)`;
}

export function rangeSelectionInsets(
  range: DiscreteRange,
  maximum: number,
): { left: string; right: string } {
  return {
    left: range.lower === 0 ? "0px" : rangePosition(range.lower, maximum),
    right:
      range.upper === maximum
        ? "0px"
        : rangePosition(maximum - range.upper, maximum),
  };
}

export function rangeIndexFromPointer(
  pointerX: number,
  trackLeft: number,
  trackWidth: number,
  maximum: number,
  thumbRadius = BRAIN_RANGE_THUMB_RADIUS_PX,
): number {
  if (maximum <= 0) return 0;
  const usableWidth = Math.max(1, trackWidth - thumbRadius * 2);
  const offset = Math.min(
    usableWidth,
    Math.max(0, pointerX - trackLeft - thumbRadius),
  );
  return Math.round((offset / usableWidth) * maximum);
}

export function nearestRangeBoundary(
  range: DiscreteRange,
  selectedIndex: number,
): RangeBoundary {
  return selectedIndex - range.lower <= range.upper - selectedIndex
    ? "lower"
    : "upper";
}

export function moveRangeBoundary(
  range: DiscreteRange,
  boundary: RangeBoundary,
  selectedIndex: number,
  limits: RangeBoundaryLimits,
): RangeBoundaryMove {
  const nextIndex = Math.max(0, Math.round(selectedIndex));

  if (boundary === "lower") {
    if (nextIndex <= range.upper) {
      return {
        boundary,
        range: {
          lower: Math.min(nextIndex, limits.lowerMaximum),
          upper: range.upper,
        },
      };
    }

    if (range.upper > limits.lowerMaximum) {
      return { boundary, range };
    }

    return {
      boundary: "upper",
      range: {
        lower: range.upper,
        upper: Math.max(
          range.upper,
          Math.min(nextIndex, limits.upperMaximum),
        ),
      },
    };
  }

  if (nextIndex >= range.lower) {
    return {
      boundary,
      range: {
        lower: range.lower,
        upper: Math.max(
          range.lower,
          Math.min(nextIndex, limits.upperMaximum),
        ),
      },
    };
  }

  return {
    boundary: "lower",
    range: {
      lower: Math.min(nextIndex, limits.lowerMaximum),
      upper: range.lower,
    },
  };
}

export function selectNearestRangeBoundary(
  range: DiscreteRange,
  selectedIndex: number,
  limits: RangeBoundaryLimits,
): DiscreteRange {
  const boundary = nearestRangeBoundary(range, selectedIndex);
  return moveRangeBoundary(range, boundary, selectedIndex, limits).range;
}
