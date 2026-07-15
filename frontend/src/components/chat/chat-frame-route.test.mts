import assert from "node:assert/strict";
import test from "node:test";

import { resolveChatFrameRoute } from "./chat-frame-route.ts";

test("Brainを背景に設定を開いてもBrainの文脈を保持する", () => {
  assert.deepEqual(resolveChatFrameRoute(["brain"]), {
    activeThreadId: undefined,
    newChatActive: false,
    product: "brain",
  });
});

test("Chatの背景ルートを一貫して導出する", () => {
  assert.deepEqual(resolveChatFrameRoute([]), {
    activeThreadId: undefined,
    newChatActive: true,
    product: "chat",
  });
  assert.deepEqual(resolveChatFrameRoute(["t", "thread-id"]), {
    activeThreadId: "thread-id",
    newChatActive: false,
    product: "chat",
  });
});

test("設定への直接アクセスはChatのフォールバック画面として扱う", () => {
  assert.deepEqual(resolveChatFrameRoute(["settings"]), {
    activeThreadId: undefined,
    newChatActive: false,
    product: "chat",
  });
});
