import assert from "node:assert/strict";
import test from "node:test";

import {
  availablePopoverSize,
  insetPopoverBoundary,
  resolvePopoverPosition,
} from "./popover-position.ts";

const viewport = {
  bottom: 844,
  left: 0,
  right: 390,
  top: 0,
};
const safeArea = { bottom: 34, left: 0, right: 0, top: 0 };

function rect({
  height,
  left,
  top,
  width,
}: {
  height: number;
  left: number;
  top: number;
  width: number;
}) {
  return {
    bottom: top + height,
    height,
    left,
    right: left + width,
    top,
    width,
  };
}

test("safe areaと衝突余白を可視領域から除外する", () => {
  const boundary = insetPopoverBoundary(viewport, safeArea, 6);

  assert.deepEqual(boundary, {
    bottom: 804,
    left: 6,
    right: 384,
    top: 6,
  });
  assert.deepEqual(availablePopoverSize(boundary), {
    height: 798,
    width: 378,
  });
});

test("下端のアカウントメニューをトリガーの上へ配置する", () => {
  const boundary = insetPopoverBoundary(viewport, safeArea, 6);

  assert.deepEqual(
    resolvePopoverPosition({
      boundary,
      content: { height: 240, width: 244 },
      gutter: 8,
      placement: "top-start",
      trigger: rect({ height: 36, left: 6, top: 764, width: 244 }),
    }),
    {
      left: 6,
      placement: "top-start",
      top: 516,
    },
  );
});

test("非同期コンテンツで高さが変わっても下端を越えない", () => {
  const boundary = insetPopoverBoundary(viewport, safeArea, 6);
  const trigger = rect({ height: 36, left: 6, top: 764, width: 244 });

  const loading = resolvePopoverPosition({
    boundary,
    content: { height: 160, width: 244 },
    gutter: 8,
    placement: "top-start",
    trigger,
  });
  const loaded = resolvePopoverPosition({
    boundary,
    content: { height: 260, width: 244 },
    gutter: 8,
    placement: "top-start",
    trigger,
  });

  assert.equal(loading.top, 596);
  assert.equal(loaded.top, 496);
  assert.ok(loaded.top + 260 <= boundary.bottom);
});

test("指定方向に収まらなければ空きの大きい反対側へ反転する", () => {
  const boundary = insetPopoverBoundary(viewport, safeArea, 6);

  assert.deepEqual(
    resolvePopoverPosition({
      boundary,
      content: { height: 180, width: 200 },
      gutter: 8,
      placement: "top-end",
      trigger: rect({ height: 36, left: 160, top: 80, width: 200 }),
    }),
    {
      left: 160,
      placement: "bottom-end",
      top: 124,
    },
  );
});

test("Visual Viewportのオフセットを含む境界内へ移動する", () => {
  const boundary = insetPopoverBoundary(
    { bottom: 760, left: 24, right: 344, top: 120 },
    { bottom: 0, left: 0, right: 0, top: 0 },
    8,
  );

  assert.deepEqual(
    resolvePopoverPosition({
      boundary,
      content: { height: 220, width: 300 },
      gutter: 8,
      placement: "bottom-start",
      trigger: rect({ height: 32, left: 4, top: 520, width: 180 }),
    }),
    {
      left: 32,
      placement: "top-start",
      top: 292,
    },
  );
});

test("コンテンツが可視領域と同じ大きさでも座標を安定させる", () => {
  const boundary = insetPopoverBoundary(viewport, safeArea, 6);
  const size = availablePopoverSize(boundary);

  assert.deepEqual(
    resolvePopoverPosition({
      boundary,
      content: size,
      gutter: 8,
      placement: "right-start",
      trigger: rect({ height: 36, left: 300, top: 400, width: 40 }),
    }),
    {
      left: boundary.left,
      placement: "left-start",
      top: boundary.top,
    },
  );
});
