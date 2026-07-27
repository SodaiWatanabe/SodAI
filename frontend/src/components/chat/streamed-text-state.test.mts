import assert from "node:assert/strict";
import test from "node:test";

import {
  appendStreamedText,
  createStreamedTextState,
  settleStreamedText,
} from "./streamed-text-state.ts";

test("累積本文の新しい差分だけを安定したsegmentとして追加する", () => {
  const initial = createStreamedTextState("考え", true);
  const continued = appendStreamedText(initial, "考えています");
  const completed = appendStreamedText(continued, "考えています。完了です");

  assert.deepEqual(completed.segments, [
    { entering: true, key: 0, text: "考え" },
    { entering: true, key: 1, text: "ています" },
    { entering: true, key: 2, text: "。完了です" },
  ]);
  assert.equal(completed.segments[0], initial.segments[0]);
  assert.equal(completed.segments[1], continued.segments[1]);
});

test("同じ本文ではsegmentを作り直さない", () => {
  const current = createStreamedTextState("思考中", true);

  assert.equal(appendStreamedText(current, "思考中"), current);
});

test("フェード済みのsegmentを次の差分追加時にまとめる", () => {
  const initial = createStreamedTextState("考え", true);
  const continued = appendStreamedText(initial, "考えています");
  const compacted = appendStreamedText(
    continued,
    "考えています。完了です",
    1,
  );

  assert.deepEqual(compacted.segments, [
    { entering: false, key: 0, text: "考えています" },
    { entering: true, key: 2, text: "。完了です" },
  ]);
});

test("累積でない本文へ変わった場合は表示を安全に置き換える", () => {
  const current = appendStreamedText(
    createStreamedTextState("古い", true),
    "古い本文",
  );

  assert.deepEqual(appendStreamedText(current, "新しい本文"), {
    animated: true,
    content: "新しい本文",
    nextKey: 3,
    segments: [{ entering: true, key: 2, text: "新しい本文" }],
  });
  assert.deepEqual(appendStreamedText(current, ""), {
    animated: true,
    content: "",
    nextKey: 3,
    segments: [],
  });
});

test("完了後は単一の通常本文へ静かに戻す", () => {
  const current = appendStreamedText(
    createStreamedTextState("思考", true),
    "思考しました",
  );

  assert.deepEqual(settleStreamedText(current), {
    animated: false,
    content: "思考しました",
    nextKey: 3,
    segments: [{ entering: false, key: 2, text: "思考しました" }],
  });
});

test("履歴として開いた通常本文にはフェード状態を作らない", () => {
  const current = createStreamedTextState("完了済みの本文", false);

  assert.deepEqual(current.segments, [
    { entering: false, key: 0, text: "完了済みの本文" },
  ]);
  assert.equal(settleStreamedText(current), current);
});
