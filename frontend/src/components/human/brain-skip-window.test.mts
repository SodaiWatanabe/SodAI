import assert from "node:assert/strict";
import test from "node:test";

import {
  isBrainSkipAllowed,
  millisecondsUntilBrainSkipCloses,
} from "./brain-skip-window.ts";

const boundary = "2026-08-01T02:00:20Z";

test("割り当てから20秒の猶予内はスキップできる", () => {
  const now = Date.parse("2026-08-01T02:00:19.999Z");

  assert.equal(isBrainSkipAllowed(boundary, now), true);
  assert.equal(millisecondsUntilBrainSkipCloses(boundary, now), 1);
});

test("猶予の境界以降はスキップできない", () => {
  assert.equal(isBrainSkipAllowed(boundary, Date.parse(boundary)), false);
  assert.equal(
    isBrainSkipAllowed(boundary, Date.parse("2026-08-01T02:00:21Z")),
    false,
  );
  assert.equal(millisecondsUntilBrainSkipCloses("invalid", 0), 0);
});
