import assert from "node:assert/strict";
import test from "node:test";

import {
  formatConditionRange,
  rangeIndices,
  valuesInRange,
} from "./human-answer-condition-range.ts";

test("選択集合から両端スライダーの範囲を復元する", () => {
  assert.deepEqual(
    rangeIndices(["lite", "standard", "pro"], ["standard", "pro"]),
    { lower: 1, upper: 2 },
  );
  assert.deepEqual(rangeIndices(["lite"], []), { lower: 0, upper: 0 });
});

test("両端を含む連続した値へ展開する", () => {
  assert.deepEqual(
    valuesInRange(["low", "medium", "high", "xhigh"], {
      lower: 1,
      upper: 3,
    }),
    ["medium", "high", "xhigh"],
  );
});

test("同じ両端は単一値、異なる両端は範囲として表示する", () => {
  const labels = ["Lite", "Standard", "Pro"];
  assert.equal(formatConditionRange(labels, { lower: 0, upper: 0 }), "Lite");
  assert.equal(
    formatConditionRange(labels, { lower: 0, upper: 2 }),
    "Lite〜Pro",
  );
});
