import assert from "node:assert/strict";
import test from "node:test";

import { shouldCommitThreadRename } from "./thread-rename-keydown.ts";

test("通常のEnterだけを会話名の保存として扱う", () => {
  assert.equal(
    shouldCommitThreadRename({
      isComposing: false,
      key: "Enter",
      keyCode: 13,
    }),
    true,
  );
  assert.equal(
    shouldCommitThreadRename({
      isComposing: false,
      key: "Escape",
      keyCode: 27,
    }),
    false,
  );
});

test("IME変換中のEnterは会話名を保存しない", () => {
  assert.equal(
    shouldCommitThreadRename({
      isComposing: true,
      key: "Enter",
      keyCode: 13,
    }),
    false,
  );
  assert.equal(
    shouldCommitThreadRename({
      isComposing: false,
      key: "Enter",
      keyCode: 229,
    }),
    false,
  );
});
