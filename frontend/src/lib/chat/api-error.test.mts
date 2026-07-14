import assert from "node:assert/strict";
import test from "node:test";

import {
  ChatApiError,
  isInsufficientCreditsError,
} from "./api-error.ts";

test("HTTP 402だけをクレジット不足として扱う", () => {
  assert.equal(
    isInsufficientCreditsError(new ChatApiError("insufficient", 402)),
    true,
  );
  assert.equal(
    isInsufficientCreditsError(new ChatApiError("unavailable", 503)),
    false,
  );
  assert.equal(isInsufficientCreditsError(new Error("network")), false);
});
