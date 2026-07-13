import assert from "node:assert/strict";
import test from "node:test";

import {
  matchesMessageSendShortcut,
  parseMessageSendPreference,
} from "./message-send.ts";

test("送信キー設定は不明な値をEnterへ戻す", () => {
  assert.equal(parseMessageSendPreference(undefined), "enter");
  assert.equal(parseMessageSendPreference("unknown"), "enter");
  assert.equal(parseMessageSendPreference("mod-enter"), "mod-enter");
});

test("Enter設定ではEnter単体で送信する", () => {
  assert.equal(
    matchesMessageSendShortcut(
      { key: "Enter", ctrlKey: false, metaKey: false },
      "enter",
    ),
    true,
  );
});

test("修飾キー設定ではCtrlまたはCommandとEnterで送信する", () => {
  assert.equal(
    matchesMessageSendShortcut(
      { key: "Enter", ctrlKey: false, metaKey: false },
      "mod-enter",
    ),
    false,
  );
  assert.equal(
    matchesMessageSendShortcut(
      { key: "Enter", ctrlKey: true, metaKey: false },
      "mod-enter",
    ),
    true,
  );
  assert.equal(
    matchesMessageSendShortcut(
      { key: "Enter", ctrlKey: false, metaKey: true },
      "mod-enter",
    ),
    true,
  );
});

test("IME変換中のEnterでは送信しない", () => {
  assert.equal(
    matchesMessageSendShortcut(
      {
        key: "Enter",
        ctrlKey: false,
        metaKey: false,
        isComposing: true,
      },
      "enter",
    ),
    false,
  );
  assert.equal(
    matchesMessageSendShortcut(
      {
        key: "Enter",
        keyCode: 229,
        ctrlKey: false,
        metaKey: false,
      },
      "enter",
    ),
    false,
  );
});
