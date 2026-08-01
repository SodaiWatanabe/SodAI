import assert from "node:assert/strict";
import test from "node:test";

import { ApiError } from "../api/api-error.ts";
import { resolveChatMutationFailure } from "./mutation-error.ts";

test("会話操作のHTTPエラーを利用者が対処できる表示へ変換する", () => {
  assert.deepEqual(resolveChatMutationFailure(new ApiError("credits", 402), "fallback"), {
    message:
      "クレジットが不足しています。アカウントメニューで無料クレジットの残量を確認できます。",
    tone: "warning",
  });
  assert.deepEqual(resolveChatMutationFailure(new ApiError("capacity", 429), "fallback"), {
    message: "現在、回答の生成が混み合っています。少し待ってからもう一度お試しください。",
    tone: "warning",
  });
  assert.deepEqual(resolveChatMutationFailure(new ApiError("unavailable", 503), "fallback"), {
    message: "回答モデルを一時的に利用できません。少し待ってからもう一度お試しください。",
    tone: "warning",
  });
  assert.deepEqual(resolveChatMutationFailure(new Error("network"), "fallback"), {
    message: "fallback",
    tone: "error",
  });
});
