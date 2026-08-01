export type PopoverPlacement =
  | "bottom-end"
  | "bottom-start"
  | "left-end"
  | "left-start"
  | "right-end"
  | "right-start"
  | "top-end"
  | "top-start";

export type PopoverRect = {
  bottom: number;
  height: number;
  left: number;
  right: number;
  top: number;
  width: number;
};

export type PopoverInsets = {
  bottom: number;
  left: number;
  right: number;
  top: number;
};

export type PopoverBoundary = Pick<
  PopoverRect,
  "bottom" | "left" | "right" | "top"
>;

type PopoverSize = Pick<PopoverRect, "height" | "width">;

const oppositeSide = {
  bottom: "top",
  left: "right",
  right: "left",
  top: "bottom",
} as const;

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(Math.max(value, minimum), Math.max(minimum, maximum));
}

export function insetPopoverBoundary(
  viewport: PopoverBoundary,
  safeArea: PopoverInsets,
  collisionPadding: number,
): PopoverBoundary {
  return {
    bottom: Math.max(
      viewport.top,
      viewport.bottom - safeArea.bottom - collisionPadding,
    ),
    left: Math.min(
      viewport.right,
      viewport.left + safeArea.left + collisionPadding,
    ),
    right: Math.max(
      viewport.left,
      viewport.right - safeArea.right - collisionPadding,
    ),
    top: Math.min(
      viewport.bottom,
      viewport.top + safeArea.top + collisionPadding,
    ),
  };
}

export function availablePopoverSize(boundary: PopoverBoundary): PopoverSize {
  return {
    height: Math.max(0, boundary.bottom - boundary.top),
    width: Math.max(0, boundary.right - boundary.left),
  };
}

export function resolvePopoverPosition({
  boundary,
  content,
  gutter,
  placement,
  trigger,
}: {
  boundary: PopoverBoundary;
  content: PopoverSize;
  gutter: number;
  placement: PopoverPlacement;
  trigger: PopoverRect;
}) {
  const [preferredSide, alignment] = placement.split("-") as [
    keyof typeof oppositeSide,
    "end" | "start",
  ];
  const spaces = {
    bottom: boundary.bottom - trigger.bottom - gutter,
    left: trigger.left - boundary.left - gutter,
    right: boundary.right - trigger.right - gutter,
    top: trigger.top - boundary.top - gutter,
  };
  const mainSize =
    preferredSide === "left" || preferredSide === "right"
      ? content.width
      : content.height;
  const alternativeSide = oppositeSide[preferredSide];
  const resolvedSide =
    spaces[preferredSide] < mainSize &&
    spaces[alternativeSide] > spaces[preferredSide]
      ? alternativeSide
      : preferredSide;
  const resolvedPlacement = `${resolvedSide}-${alignment}` as PopoverPlacement;

  let left: number;
  let top: number;
  if (resolvedSide === "top" || resolvedSide === "bottom") {
    left =
      alignment === "start"
        ? trigger.left
        : trigger.right - content.width;
    top =
      resolvedSide === "top"
        ? trigger.top - gutter - content.height
        : trigger.bottom + gutter;
  } else {
    left =
      resolvedSide === "left"
        ? trigger.left - gutter - content.width
        : trigger.right + gutter;
    top =
      alignment === "start"
        ? trigger.top
        : trigger.bottom - content.height;
  }

  return {
    left: clamp(left, boundary.left, boundary.right - content.width),
    placement: resolvedPlacement,
    top: clamp(top, boundary.top, boundary.bottom - content.height),
  };
}
