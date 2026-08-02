import assert from "node:assert/strict";
import test from "node:test";

import { resolveVisualViewportFrame } from "./visual-viewport.ts";

test("Visual Viewportの表示境界をLayout Viewport座標へ変換する", () => {
  assert.deepEqual(
    resolveVisualViewportFrame(
      {
        height: 390,
        offsetLeft: 4,
        offsetTop: 82,
        scale: 1,
        width: 382,
      },
      { height: 844, width: 390 },
    ),
    {
      bottom: 472,
      height: 390,
      left: 4,
      right: 386,
      scale: 1,
      top: 82,
      width: 382,
    },
  );
});

test("Visual Viewportがない環境ではLayout Viewportを使用する", () => {
  assert.deepEqual(resolveVisualViewportFrame(null, { height: 720, width: 1280 }), {
    bottom: 720,
    height: 720,
    left: 0,
    right: 1280,
    scale: 1,
    top: 0,
    width: 1280,
  });
});

test("不正なVisual Viewport値を安全なLayout Viewport値へ戻す", () => {
  assert.deepEqual(
    resolveVisualViewportFrame(
      {
        height: 0,
        offsetLeft: Number.NaN,
        offsetTop: -20,
        scale: 0,
        width: Number.NaN,
      },
      { height: 640, width: 360 },
    ),
    {
      bottom: 640,
      height: 640,
      left: 0,
      right: 360,
      scale: 1,
      top: 0,
      width: 360,
    },
  );
});
