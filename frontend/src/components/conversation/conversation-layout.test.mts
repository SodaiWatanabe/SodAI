import assert from "node:assert/strict";
import test from "node:test";

import { getConversationMessageLayout } from "./conversation-layout.ts";

test("Chatではプロンプターを右バブル、回答を左生成本文にする", () => {
  assert.deepEqual(getConversationMessageLayout("human", "prompter"), {
    side: "right",
    surface: "bubble",
  });
  assert.deepEqual(getConversationMessageLayout("model", "prompter"), {
    side: "left",
    surface: "generated",
  });
});

test("Brainではプロンプターの左バブルと回答本文の左端を揃える", () => {
  assert.deepEqual(getConversationMessageLayout("human", "answerer"), {
    side: "left",
    surface: "bubble",
  });
  assert.deepEqual(getConversationMessageLayout("model", "answerer"), {
    side: "left",
    surface: "generated",
  });
});
