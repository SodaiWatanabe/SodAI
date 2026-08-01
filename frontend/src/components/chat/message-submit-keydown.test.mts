import assert from "node:assert/strict";
import test from "node:test";

import { shouldSubmitMessageFromKeyboard } from "./message-submit-keydown-policy.ts";

test("PCでは設定されたEnterでメッセージを送信する", () => {
  assert.equal(
    shouldSubmitMessageFromKeyboard({
      coarsePrimaryPointer: false,
      enabled: true,
      shortcutMatches: true,
    }),
    true,
  );
});

test("スマホではEnterを送信に使わず改行を維持する", () => {
  assert.equal(
    shouldSubmitMessageFromKeyboard({
      coarsePrimaryPointer: true,
      enabled: true,
      shortcutMatches: true,
    }),
    false,
  );
});
