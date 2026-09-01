import assert from "node:assert/strict";
import test from "node:test";

import {
  IDLE_RESPONSE_OPERATION,
  requestResponseCancellation,
  responseCanRegenerate,
  resolveCreatedExecution,
  resolveTerminalExecution,
} from "./response-operation.ts";

test("提供終了したAnswererの履歴には再生成操作を出さない", () => {
  const available = new Set(["asuka-1.1", "hina"]);

  assert.equal(responseCanRegenerate("completed", "asuka-1", available), false);
  assert.equal(responseCanRegenerate("completed", "asuka-1.1", available), true);
  assert.equal(responseCanRegenerate("failed", "asuka-1.1", available), false);
});

test("作成中の停止要求をExecution確定まで保持する", () => {
  const waiting = requestResponseCancellation({ kind: "creating" });

  assert.deepEqual(waiting, { kind: "waiting-for-execution-to-cancel" });
  assert.deepEqual(resolveCreatedExecution(waiting, "execution"), {
    kind: "cancelling",
    executionId: "execution",
  });
});

test("再生成中の停止要求もExecution確定まで保持する", () => {
  const waiting = requestResponseCancellation({
    kind: "regenerating",
    responseRequestId: "response",
  });

  assert.deepEqual(waiting, { kind: "waiting-for-execution-to-cancel" });
  assert.deepEqual(resolveCreatedExecution(waiting, "execution"), {
    kind: "cancelling",
    executionId: "execution",
  });
});

test("既知のExecutionは直ちに停止対象へする", () => {
  assert.deepEqual(
    requestResponseCancellation(IDLE_RESPONSE_OPERATION, "execution"),
    { kind: "cancelling", executionId: "execution" },
  );
});

test("停止中の二重操作で対象Executionを変更しない", () => {
  const cancelling = { kind: "cancelling", executionId: "first" } as const;

  assert.equal(
    requestResponseCancellation(cancelling, "second"),
    cancelling,
  );
  assert.equal(resolveCreatedExecution(cancelling, "first"), cancelling);
});

test("同じExecutionの終端eventで停止操作を完了する", () => {
  const cancelling = { kind: "cancelling", executionId: "execution" } as const;

  assert.equal(resolveTerminalExecution(cancelling, "execution").kind, "idle");
  assert.equal(resolveTerminalExecution(cancelling, "other"), cancelling);
});
