import assert from "node:assert/strict";
import test from "node:test";

import {
  moveRangeBoundary,
  nearestRangeBoundary,
  rangeIndexFromPointer,
  rangePosition,
  rangeSelectionInsets,
  selectNearestRangeBoundary,
} from "./brain-range-slider-model.ts";

test("つまみ半径を含めて段階位置を算出する", () => {
  assert.equal(rangePosition(0, 4), "calc(0% + 14px)");
  assert.equal(rangePosition(2, 4), "calc(50% + 0px)");
  assert.equal(rangePosition(4, 4), "calc(100% - 14px)");
  assert.deepEqual(rangeSelectionInsets({ lower: 0, upper: 4 }, 4), {
    left: "0px",
    right: "0px",
  });
});

test("ポインター位置を最も近い段階へ収める", () => {
  assert.equal(rangeIndexFromPointer(0, 0, 228, 4), 0);
  assert.equal(rangeIndexFromPointer(114, 0, 228, 4), 2);
  assert.equal(rangeIndexFromPointer(300, 0, 228, 4), 4);
});

test("選択位置に近い境界だけを移動する", () => {
  const limits = { lowerMaximum: 3, upperMaximum: 4 };
  assert.deepEqual(
    selectNearestRangeBoundary({ lower: 1, upper: 3 }, 0, limits),
    { lower: 0, upper: 3 },
  );
  assert.deepEqual(
    selectNearestRangeBoundary({ lower: 1, upper: 3 }, 2, limits),
    { lower: 2, upper: 3 },
  );
  assert.deepEqual(
    selectNearestRangeBoundary({ lower: 1, upper: 3 }, 4, limits),
    { lower: 1, upper: 4 },
  );
});

test("ドラッグした境界が反対側を越えると役割を入れ替える", () => {
  const limits = { lowerMaximum: 4, upperMaximum: 4 };

  assert.deepEqual(
    moveRangeBoundary({ lower: 1, upper: 3 }, "upper", 0, limits),
    { boundary: "lower", range: { lower: 0, upper: 1 } },
  );
  assert.deepEqual(
    moveRangeBoundary({ lower: 1, upper: 3 }, "lower", 4, limits),
    { boundary: "upper", range: { lower: 3, upper: 4 } },
  );
});

test("境界の役割交換後も新しい境界を連続して動かせる", () => {
  const limits = { lowerMaximum: 4, upperMaximum: 4 };
  const crossed = moveRangeBoundary(
    { lower: 2, upper: 4 },
    "upper",
    1,
    limits,
  );

  assert.deepEqual(
    moveRangeBoundary(crossed.range, crossed.boundary, 0, limits),
    { boundary: "lower", range: { lower: 0, upper: 2 } },
  );
});

test("最も近い境界を選び同距離では下限を優先する", () => {
  assert.equal(nearestRangeBoundary({ lower: 1, upper: 4 }, 0), "lower");
  assert.equal(nearestRangeBoundary({ lower: 1, upper: 4 }, 3), "upper");
  assert.equal(nearestRangeBoundary({ lower: 2, upper: 2 }, 2), "lower");
});
