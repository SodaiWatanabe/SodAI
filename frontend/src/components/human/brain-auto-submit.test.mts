import assert from "node:assert/strict";
import test from "node:test";

import {
  BRAIN_AUTO_SUBMIT_LEAD_MS,
  millisecondsUntilBrainAutoSubmit,
} from "./brain-auto-submit.ts";

const deadline = "2026-08-01T03:00:00Z";

test("通信時間を確保して回答期限の直前に自動送信する", () => {
  const now = Date.parse(deadline) - 1_000;

  assert.equal(
    millisecondsUntilBrainAutoSubmit(deadline, now),
    1_000 - BRAIN_AUTO_SUBMIT_LEAD_MS,
  );
});

test("期限直前または不正な期限は直ちに自動送信判定する", () => {
  assert.equal(
    millisecondsUntilBrainAutoSubmit(
      deadline,
      Date.parse(deadline) - BRAIN_AUTO_SUBMIT_LEAD_MS,
    ),
    0,
  );
  assert.equal(millisecondsUntilBrainAutoSubmit("invalid", 0), 0);
});
