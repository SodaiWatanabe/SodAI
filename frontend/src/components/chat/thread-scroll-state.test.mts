import assert from "node:assert/strict";
import test from "node:test";

import {
  calculateTurnScrollLayout,
  transitionThreadScrollMode,
} from "./thread-scroll-state.ts";

test("送信ターンと手動スクロールを独立した状態として遷移する", () => {
  assert.equal(transitionThreadScrollMode("bottom", "anchor-turn"), "turn");
  assert.equal(transitionThreadScrollMode("turn", "detach"), "detached");
  assert.equal(
    transitionThreadScrollMode("detached", "pin-bottom"),
    "bottom",
  );
});

test("既に下側の余裕がある場合は送信ターン用の余白を加えない", () => {
  assert.deepEqual(
    calculateTurnScrollLayout({
      containerHeight: 600,
      containerScrollTop: 1_000,
      containerTop: 0,
      entryTop: 200,
      scrollHeight: 2_000,
      scrollMarginTop: 96,
      spacerHeight: 0,
    }),
    {
      scrollTop: 1_104,
      spacerHeight: 0,
    },
  );
});

test("短い会話でもバブルを上部へ置けるだけの余白を算出する", () => {
  assert.deepEqual(
    calculateTurnScrollLayout({
      containerHeight: 700,
      containerScrollTop: 300,
      containerTop: 100,
      entryTop: 500,
      scrollHeight: 1_000,
      scrollMarginTop: 96,
      spacerHeight: 0,
    }),
    {
      scrollTop: 604,
      spacerHeight: 304,
    },
  );
});

test("回答が伸びた分だけ送信ターン用の余白を縮める", () => {
  assert.deepEqual(
    calculateTurnScrollLayout({
      containerHeight: 700,
      containerScrollTop: 604,
      containerTop: 100,
      entryTop: 196,
      scrollHeight: 1_504,
      scrollMarginTop: 96,
      spacerHeight: 304,
    }),
    {
      scrollTop: 604,
      spacerHeight: 104,
    },
  );
});

test("表示領域が広がった場合はバブル位置を戻せるよう余白を増やす", () => {
  assert.deepEqual(
    calculateTurnScrollLayout({
      containerHeight: 500,
      containerScrollTop: 400,
      containerTop: 0,
      entryTop: 196,
      scrollHeight: 900,
      scrollMarginTop: 96,
      spacerHeight: 100,
    }),
    {
      scrollTop: 500,
      spacerHeight: 200,
    },
  );
});

test("上端より上を要求する場合はスクロール位置を0に収める", () => {
  assert.deepEqual(
    calculateTurnScrollLayout({
      containerHeight: 500,
      containerScrollTop: 0,
      containerTop: 100,
      entryTop: 120,
      scrollHeight: 500,
      scrollMarginTop: 96,
      spacerHeight: 0,
    }),
    {
      scrollTop: 0,
      spacerHeight: 0,
    },
  );
});
