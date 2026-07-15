import assert from "node:assert/strict";
import test from "node:test";

import { ApiError, isApiErrorStatus } from "./api-error.ts";

test("指定したHTTP statusのAPIエラーだけを扱う", () => {
  assert.equal(isApiErrorStatus(new ApiError("insufficient", 402), 402), true);
  assert.equal(isApiErrorStatus(new ApiError("unavailable", 503), 402), false);
  assert.equal(isApiErrorStatus(new Error("network"), 402), false);
});
