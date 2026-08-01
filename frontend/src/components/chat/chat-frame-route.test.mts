import assert from "node:assert/strict";
import test from "node:test";

import { resolveChatFrameRoute } from "./chat-frame-route.ts";

test("Brainを背景に設定を開いてもBrainの文脈を保持する", () => {
  assert.deepEqual(resolveChatFrameRoute(["brain"]), {
    activeHumanAnswerId: undefined,
    activeThreadId: undefined,
    newChatActive: false,
    product: "brain",
  });
});

test("Brainの回答履歴を選択中の回答IDまで導出する", () => {
  assert.deepEqual(
    resolveChatFrameRoute(["brain", "answers", "execution-id"]),
    {
      activeHumanAnswerId: "execution-id",
      activeThreadId: undefined,
      newChatActive: false,
      product: "brain",
    },
  );
});

test("Chatの背景ルートを一貫して導出する", () => {
  assert.deepEqual(resolveChatFrameRoute([]), {
    activeHumanAnswerId: undefined,
    activeThreadId: undefined,
    newChatActive: true,
    product: "chat",
  });
  assert.deepEqual(resolveChatFrameRoute(["t", "thread-id"]), {
    activeHumanAnswerId: undefined,
    activeThreadId: "thread-id",
    newChatActive: false,
    product: "chat",
  });
});

test("設定への直接アクセスはChatのフォールバック画面として扱う", () => {
  assert.deepEqual(resolveChatFrameRoute(["settings"]), {
    activeHumanAnswerId: undefined,
    activeThreadId: undefined,
    newChatActive: false,
    product: "chat",
  });
});
