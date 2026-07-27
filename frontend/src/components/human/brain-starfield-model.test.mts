import assert from "node:assert/strict";
import test from "node:test";

import {
  createBrainStarfield,
  isInsideBrainStarfieldQuietZone,
  resolveBrainStarAlpha,
} from "./brain-starfield-model.ts";

test("同じseedと画面サイズから安定した星群を生成する", () => {
  const first = createBrainStarfield(1200, 800, 42);
  const second = createBrainStarfield(1200, 800, 42);

  assert.deepEqual(first, second);
  assert.ok(first.length >= 96);
  assert.ok(first.length <= 220);
});

test("画面サイズに応じて星の数を安全な範囲で調整する", () => {
  const mobile = createBrainStarfield(390, 720, 84);
  const desktop = createBrainStarfield(1440, 1000, 84);
  const veryLarge = createBrainStarfield(7680, 4320, 84);

  assert.equal(mobile.length, 96);
  assert.ok(desktop.length > mobile.length);
  assert.equal(veryLarge.length, 220);
});

test("中央の操作領域では星の密度を抑える", () => {
  const stars = createBrainStarfield(1440, 1000, 126);
  const centralStars = stars.filter(({ x, y }) =>
    isInsideBrainStarfieldQuietZone(x, y),
  );

  assert.ok(centralStars.length < stars.length * 0.04);
});

test("星の描画値を有効な範囲へ収める", () => {
  const stars = createBrainStarfield(1200, 800, 168);

  for (const star of stars) {
    assert.ok(star.x >= 0 && star.x <= 1);
    assert.ok(star.y >= 0 && star.y <= 1);
    assert.ok(star.alpha > 0 && star.alpha <= 1);
    assert.ok(star.radius > 0);
    assert.ok(Number.isFinite(star.driftX));
    assert.ok(Number.isFinite(star.driftY));
  }
});

test("一部の星だけに明確な瞬きを持たせる", () => {
  const stars = createBrainStarfield(1440, 1000, 210);
  const pronounced = stars.filter(
    ({ twinkleAmount }) => twinkleAmount >= 0.5,
  );
  const subtle = stars.filter(
    ({ twinkleAmount }) => twinkleAmount < 0.5,
  );

  assert.ok(pronounced.length > 0);
  assert.ok(subtle.length > pronounced.length);
  assert.ok(pronounced.every(({ twinkleAmount }) => twinkleAmount <= 0.8));
});

test("強い瞬きは暗部と発光部の差を明確にする", () => {
  const star = {
    alpha: 0.4,
    depth: 0.5,
    driftX: 0,
    driftY: 0,
    glow: true,
    phase: -Math.PI / 2,
    radius: 1,
    twinkleAmount: 0.6,
    twinkleSpeed: 1,
    x: 0.5,
    y: 0.5,
  };

  const dimmed = resolveBrainStarAlpha(star, 0);
  const illuminated = resolveBrainStarAlpha(star, Math.PI);

  assert.ok(dimmed < 0.1);
  assert.ok(illuminated > 0.8);
});
