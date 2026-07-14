import assert from "node:assert/strict";
import test from "node:test";

import {
  creditAllowanceRemainingRatio,
  formatCreditAmount,
  formatCreditResetDate,
  presentFreeCreditAllowance,
  presentCreditTransaction,
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
  assert.deepEqual(presentFreeCreditAllowance(null, displayedAt), {
    remainingPercent: 100,
    resetAt: new Date("2026-07-21T06:30:00.000Z"),
  });
});

test("開始済みの無料枠は残量0でもサーバーの期日を維持する", () => {
  const expiresAt = "2026-07-20T15:00:00Z";

  assert.deepEqual(
    presentFreeCreditAllowance(
      {
        limit: 20_000_000,
        used: 20_000_000,
        reserved: 0,
        remaining: 0,
        starts_at: "2026-07-13T15:00:00Z",
        expires_at: expiresAt,
      },
      new Date("2026-07-14T06:30:00Z"),
    ),
    { remainingPercent: 0, resetAt: expiresAt },
  );
});

test("リセット期日は月日だけを日本語で表示する", () => {
  const display = formatCreditResetDate(
    "2026-07-19T15:00:00Z",
    "Asia/Tokyo",
  );

  assert.equal(display, "7月20日");
});

test("クレジット金額はscaleに従って表示する", () => {
  assert.equal(formatCreditAmount(20_000_000, 1_000_000), "20");
  assert.equal(formatCreditAmount(100_000, 1_000_000), "0.1");
  assert.equal(formatCreditAmount(100_000, 1_000_000, true), "+0.1");
});

test("確定取引は予約額と返却額から実消費額を表示する", () => {
  assert.deepEqual(
    presentCreditTransaction({
      id: "transaction",
      kind: "settle",
      available_delta: 100_000,
      reserved_delta: -200_000,
      source_kind: null,
      expires_at: null,
      created_at: "2026-07-14T06:30:00Z",
    }),
    { amount: -100_000, label: "モデルの利用", tone: "decrease" },
  );
});
