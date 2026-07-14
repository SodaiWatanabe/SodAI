import assert from "node:assert/strict";
import test from "node:test";

import {
  creditAllowanceRemainingRatio,
  formatCreditResetDate,
  projectFreeAllowanceExpiry,
} from "./presentation.ts";

test("無料枠の残量率は利用に応じて減り表示範囲へ収める", () => {
  assert.equal(
    creditAllowanceRemainingRatio({ limit: 20, remaining: 14 }),
    0.7,
  );
  assert.equal(
    creditAllowanceRemainingRatio({ limit: 20, remaining: 21 }),
    1,
  );
  assert.equal(
    creditAllowanceRemainingRatio({ limit: 20, remaining: -1 }),
    0,
  );
  assert.equal(
    creditAllowanceRemainingRatio({ limit: 0, remaining: 0 }),
    0,
  );
});

test("未開始の無料枠は表示時点から168時間後を期限候補にする", () => {
  const displayedAt = new Date("2026-07-14T06:30:00Z");

  assert.equal(
    projectFreeAllowanceExpiry(displayedAt).toISOString(),
    "2026-07-21T06:30:00.000Z",
  );
});

test("リセット期日は月日だけを日本語で表示する", () => {
  const display = formatCreditResetDate(
    "2026-07-19T15:00:00Z",
    "Asia/Tokyo",
  );

  assert.equal(display, "7月20日");
});
