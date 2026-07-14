import assert from "node:assert/strict";
import test from "node:test";

import {
  createKeyboardShortcutCookie,
  DEFAULT_KEYBOARD_SHORTCUTS,
  formatKeyboardShortcut,
  isDefaultKeyboardShortcut,
  keyboardShortcutFromKey,
  keyboardShortcutsConflict,
  matchesKeyboardShortcut,
  parseKeyboardShortcuts,
  validateKeyboardShortcut,
  type KeyboardShortcut,
} from "./keyboard-shortcuts.ts";

const key = (
  overrides: Partial<{
    altKey: boolean;
    ctrlKey: boolean;
    isComposing: boolean;
    key: string;
    keyCode: number;
    metaKey: boolean;
    shiftKey: boolean;
  }> = {},
) => ({
  altKey: false,
  ctrlKey: false,
  key: "Enter",
  metaKey: false,
  shiftKey: false,
  ...overrides,
});

const shortcut = (
  overrides: Partial<KeyboardShortcut> = {},
): KeyboardShortcut => ({
  altKey: false,
  ctrlKey: false,
  key: "Enter",
  metaKey: false,
  modifierMode: "exact",
  shiftKey: false,
  ...overrides,
});

test("送信の旧設定を維持し新しい会話は未設定へ戻す", () => {
  assert.deepEqual(
    parseKeyboardShortcuts({ messageSend: undefined, newChat: undefined }),
    DEFAULT_KEYBOARD_SHORTCUTS,
  );
  const parsed = parseKeyboardShortcuts({
    messageSend: "mod-enter",
    newChat: "unknown",
  });
  assert.equal(formatKeyboardShortcut(parsed.messageSend!), "Ctrl / ⌘ + Enter");
  assert.equal(parsed.newChat, null);
});

test("ショートカットをアクション別Cookieへ保存する", () => {
  const custom = shortcut({ ctrlKey: true, key: "k", shiftKey: true });
  assert.match(
    createKeyboardShortcutCookie("newChat", custom, true),
    /^sodai_new_chat_key=v2\.9\.6b; Path=\/; Max-Age=31536000; SameSite=Lax; Secure$/,
  );
  assert.equal(
    createKeyboardShortcutCookie("newChat", null, false),
    "sodai_new_chat_key=; Path=/; Max-Age=0; SameSite=Lax",
  );
  assert.match(
    createKeyboardShortcutCookie(
      "messageSend",
      DEFAULT_KEYBOARD_SHORTCUTS.messageSend,
      false,
    ),
    /^sodai_message_send_key=enter;/,
  );
});

test("修飾キー単体は記録せず配列に応じた入力キーを記録する", () => {
  assert.equal(
    keyboardShortcutFromKey(key({ ctrlKey: true, key: "Control" })),
    null,
  );
  assert.deepEqual(
    keyboardShortcutFromKey(key({ key: "/", metaKey: true })),
    shortcut({ key: "/", metaKey: true }),
  );
  assert.equal(
    formatKeyboardShortcut(shortcut({ ctrlKey: true, key: "@" })),
    "Ctrl + @",
  );
});

test("新しい会話にはCtrl、Command、Altのいずれかを必須にする", () => {
  const current = DEFAULT_KEYBOARD_SHORTCUTS;
  assert.deepEqual(
    validateKeyboardShortcut(
      current,
      "newChat",
      shortcut({ key: "n", shiftKey: true }),
    ),
    { ok: false, reason: "modifier-required" },
  );
  assert.deepEqual(
    validateKeyboardShortcut(
      current,
      "newChat",
      shortcut({ key: "n", altKey: true }),
    ),
    { ok: true },
  );
});

test("送信はEnter以外の無修飾キーで本文入力を奪わない", () => {
  assert.deepEqual(
    validateKeyboardShortcut(
      DEFAULT_KEYBOARD_SHORTCUTS,
      "messageSend",
      shortcut({ key: "Backspace" }),
    ),
    { ok: false, reason: "modifier-required" },
  );
  assert.deepEqual(
    validateKeyboardShortcut(
      DEFAULT_KEYBOARD_SHORTCUTS,
      "messageSend",
      shortcut({ key: "Enter", shiftKey: true }),
    ),
    { ok: true },
  );
  assert.deepEqual(
    parseKeyboardShortcuts({
      messageSend: "v2.0.61",
      newChat: undefined,
    }).messageSend,
    DEFAULT_KEYBOARD_SHORTCUTS.messageSend,
  );
});

test("抽象的なCtrlまたはCommand設定との実競合も検出する", () => {
  const legacy = parseKeyboardShortcuts({
    messageSend: "mod-enter",
    newChat: undefined,
  }).messageSend!;
  const controlEnter = shortcut({ ctrlKey: true });
  const commandEnter = shortcut({ metaKey: true });
  assert.equal(keyboardShortcutsConflict(legacy, controlEnter), true);
  assert.equal(keyboardShortcutsConflict(legacy, commandEnter), true);
  assert.deepEqual(
    validateKeyboardShortcut(
      { messageSend: legacy, newChat: null },
      "newChat",
      controlEnter,
    ),
    { conflictingAction: "messageSend", ok: false, reason: "conflict" },
  );
});

test("リセットで他のアクションとの競合を再生成しない", () => {
  assert.deepEqual(
    validateKeyboardShortcut(
      {
        messageSend: shortcut({ ctrlKey: true, key: "k" }),
        newChat: shortcut({ ctrlKey: true }),
      },
      "messageSend",
      DEFAULT_KEYBOARD_SHORTCUTS.messageSend,
    ),
    { conflictingAction: "newChat", ok: false, reason: "conflict" },
  );
});

test("保存済みの新しい会話が競合または修飾キーなしなら無効化する", () => {
  assert.equal(
    parseKeyboardShortcuts({
      messageSend: "enter",
      newChat: "v2.0.45-6e-74-65-72",
    }).newChat,
    null,
  );
  assert.equal(
    parseKeyboardShortcuts({
      messageSend: "mod-enter",
      newChat: "v2.1.45-6e-74-65-72",
    }).newChat,
    null,
  );
  assert.deepEqual(
    parseKeyboardShortcuts({
      messageSend: "enter",
      newChat: "v2.1.6e",
    }).newChat,
    shortcut({ ctrlKey: true, key: "n" }),
  );
});

test("キーと修飾キーが完全に一致したときだけ実行する", () => {
  const custom = shortcut({ ctrlKey: true, key: "k", shiftKey: true });
  assert.equal(
    matchesKeyboardShortcut(
      key({ ctrlKey: true, key: "K", shiftKey: true }),
      custom,
    ),
    true,
  );
  assert.equal(
    matchesKeyboardShortcut(
      key({ ctrlKey: true, key: "k" }),
      custom,
    ),
    false,
  );
});

test("従来のEnter設定は既存の修飾キー判定を維持する", () => {
  const enter = DEFAULT_KEYBOARD_SHORTCUTS.messageSend;
  const primaryEnter = parseKeyboardShortcuts({
    messageSend: "mod-enter",
    newChat: undefined,
  }).messageSend;

  assert.equal(matchesKeyboardShortcut(key({ ctrlKey: true }), enter), true);
  assert.equal(matchesKeyboardShortcut(key({ key: "Enter" }), enter), true);
  assert.equal(
    matchesKeyboardShortcut(key({ ctrlKey: true, shiftKey: true }), enter),
    false,
  );
  assert.equal(
    matchesKeyboardShortcut(
      key({ altKey: true, ctrlKey: true, shiftKey: true }),
      primaryEnter,
    ),
    true,
  );
});

test("IME変換中は一致するショートカットを実行しない", () => {
  assert.equal(keyboardShortcutFromKey(key({ isComposing: true })), null);
  assert.equal(keyboardShortcutFromKey(key({ keyCode: 229 })), null);
  assert.equal(
    matchesKeyboardShortcut(
      key({ isComposing: true }),
      DEFAULT_KEYBOARD_SHORTCUTS.messageSend!,
    ),
    false,
  );
  assert.equal(
    matchesKeyboardShortcut(
      key({ keyCode: 229 }),
      DEFAULT_KEYBOARD_SHORTCUTS.messageSend!,
    ),
    false,
  );
});

test("各アクションの初期値を判定する", () => {
  assert.equal(
    isDefaultKeyboardShortcut(
      "messageSend",
      DEFAULT_KEYBOARD_SHORTCUTS.messageSend,
    ),
    true,
  );
  assert.equal(isDefaultKeyboardShortcut("newChat", null), true);
  assert.equal(
    isDefaultKeyboardShortcut(
      "newChat",
      shortcut({ ctrlKey: true, key: "n" }),
    ),
    false,
  );
});
