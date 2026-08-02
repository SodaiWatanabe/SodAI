export type VisualViewportFrame = {
  bottom: number;
  height: number;
  left: number;
  right: number;
  scale: number;
  top: number;
  width: number;
};

type VisualViewportGeometry = {
  height: number;
  offsetLeft: number;
  offsetTop: number;
  scale: number;
  width: number;
};

type LayoutViewportSize = {
  height: number;
  width: number;
};

function finiteOr(value: number | undefined, fallback: number) {
  return value !== undefined && Number.isFinite(value) ? value : fallback;
}

function positiveOr(value: number | undefined, fallback: number) {
  const resolved = finiteOr(value, fallback);
  return resolved > 0 ? resolved : fallback;
}

export function resolveVisualViewportFrame(
  viewport: VisualViewportGeometry | null | undefined,
  layout: LayoutViewportSize,
): VisualViewportFrame {
  const fallbackHeight = Math.max(0, finiteOr(layout.height, 0));
  const fallbackWidth = Math.max(0, finiteOr(layout.width, 0));
  const height = positiveOr(viewport?.height, fallbackHeight);
  const width = positiveOr(viewport?.width, fallbackWidth);
  const left = Math.max(0, finiteOr(viewport?.offsetLeft, 0));
  const top = Math.max(0, finiteOr(viewport?.offsetTop, 0));

  return {
    bottom: top + height,
    height,
    left,
    right: left + width,
    scale: positiveOr(viewport?.scale, 1),
    top,
    width,
  };
}

export function readVisualViewportFrame(): VisualViewportFrame {
  return resolveVisualViewportFrame(window.visualViewport, {
    height: document.documentElement.clientHeight,
    width: document.documentElement.clientWidth,
  });
}

export function visualViewportFramesEqual(
  left: VisualViewportFrame | null,
  right: VisualViewportFrame,
) {
  return (
    left?.height === right.height &&
    left.left === right.left &&
    left.scale === right.scale &&
    left.top === right.top &&
    left.width === right.width
  );
}
