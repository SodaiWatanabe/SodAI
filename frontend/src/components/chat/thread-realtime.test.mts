import assert from "node:assert/strict";
import test from "node:test";

import type { RealtimeEvent, Thread } from "../../lib/chat/types.ts";
import {
  mergeExecutionSnapshot,
  reduceThreadRealtime,
} from "./thread-realtime.ts";

const thread: Thread = {
  id: "thread",
  space_id: "space",
  title: "会話",
  answerer: "asuka-1",
  revision: 3,
  created_at: "2026-07-13T00:00:00Z",
  updated_at: "2026-07-13T00:00:00Z",
  last_activity_at: "2026-07-13T00:00:00Z",
  entries: [],
  latest_response: {
    id: "request",
    thread_id: "thread",
    input_entry_id: "entry",
    requested_answerer: "asuka-1",
    reasoning_effort: "none",
    target_actor: { id: "asuka-1", kind: "model", name: "Asuka 1" },
    status: "running",
    created_at: "2026-07-13T00:00:00Z",
    execution: {
      id: "execution-2",
      response_request_id: "request",
      thread_id: "thread",
      result_entry_id: null,
      answerer: "asuka-1",
      target: "local:asuka-1",
      status: "running",
      attempt_no: 2,
      attempt_id: "attempt-2",
      partial_output: "途中",
      resolved_model: "asuka-1@artifact",
      generation_phase: "thinking",
      error_code: null,
      created_at: "2026-07-13T00:00:00Z",
      evaluation: null,
    },
  },
};

function event(
  type: RealtimeEvent["type"],
  overrides: Partial<RealtimeEvent> = {},
): RealtimeEvent {
  return {
    id: "event",
    sequence: 1,
    type,
    space_id: "space",
    thread_id: "thread",
    thread_revision: 4,
    response_request_id: "request",
    execution_id: "execution-2",
    occurred_at: "2026-07-13T00:00:01Z",
    data: {},
    ...overrides,
  };
}

test("response.queuedは最新ExecutionをHTTPで同期する", () => {
  const decision = reduceThreadRealtime(thread, event("response.queued"));
  assert.equal(decision.shouldSync, true);
  assert.equal(decision.next, thread);
});

test("旧Executionの遅延eventを本文へ混ぜない", () => {
  const decision = reduceThreadRealtime(
    thread,
    event("response.delta", {
      execution_id: "execution-1",
      data: { content: "古い本文" },
    }),
  );
  assert.equal(decision.shouldSync, true);
  assert.equal(decision.next, thread);
});

test("現在Executionの累積本文を置換する", () => {
  const decision = reduceThreadRealtime(
    thread,
    event("response.delta", { data: { content: "途中までの本文" } }),
  );
  assert.equal(decision.shouldSync, false);
  assert.equal(decision.next?.latest_response?.execution.partial_output, "途中までの本文");
  assert.equal(
    decision.next?.latest_response?.execution.generation_phase,
    "answering",
  );
});

test("phase eventは本文を変えずに回答状態へ単調遷移する", () => {
  const decision = reduceThreadRealtime(
    thread,
    event("response.phase", { data: { phase: "answering" } }),
  );

  assert.equal(decision.shouldSync, false);
  assert.equal(decision.next?.latest_response?.execution.partial_output, "途中");
  assert.equal(
    decision.next?.latest_response?.execution.generation_phase,
    "answering",
  );
});

test("phase eventでthinkingへ逆戻りしない", () => {
  const answering: Thread = {
    ...thread,
    latest_response: {
      ...thread.latest_response!,
      execution: {
        ...thread.latest_response!.execution,
        generation_phase: "answering",
      },
    },
  };
  const decision = reduceThreadRealtime(
    answering,
    event("response.phase", { data: { phase: "thinking" } }),
  );

  assert.equal(
    decision.next?.latest_response?.execution.generation_phase,
    "answering",
  );
});

test("terminal eventを反映したあと確定EntryをHTTP同期する", () => {
  const decision = reduceThreadRealtime(
    thread,
    event("response.completed", {
      data: { content: "完了", result_entry_id: "result" },
    }),
  );
  assert.equal(decision.next?.latest_response?.status, "completed");
  assert.equal(decision.next?.latest_response?.execution.result_entry_id, "result");
  assert.equal(decision.next?.latest_response?.execution.generation_phase, null);
  assert.equal(decision.shouldSync, true);
});

test("停止eventは部分本文を保ったcancelled状態として反映する", () => {
  const decision = reduceThreadRealtime(
    thread,
    event("response.cancelled", {
      data: { content: "途中まで", result_entry_id: "partial-result" },
    }),
  );

  assert.equal(decision.next?.latest_response?.status, "cancelled");
  assert.equal(decision.next?.latest_response?.execution.status, "cancelled");
  assert.equal(
    decision.next?.latest_response?.execution.partial_output,
    "途中まで",
  );
  assert.equal(
    decision.next?.latest_response?.execution.result_entry_id,
    "partial-result",
  );
  assert.equal(decision.shouldSync, true);
});

test("停止後の遅延deltaで終端状態や本文を巻き戻さない", () => {
  const cancelled = reduceThreadRealtime(
    thread,
    event("response.cancelled", { data: { content: "確定した途中本文" } }),
  ).next!;
  const late = reduceThreadRealtime(
    cancelled,
    event("response.delta", {
      thread_revision: cancelled.revision,
      data: { content: "遅延本文" },
    }),
  );

  assert.equal(late.next, cancelled);
  assert.equal(late.next?.latest_response?.status, "cancelled");
  assert.equal(
    late.next?.latest_response?.execution.partial_output,
    "確定した途中本文",
  );
});

test("停止後の遅延terminal eventでもcancelledを巻き戻さない", () => {
  const cancelled = reduceThreadRealtime(
    thread,
    event("response.cancelled", { data: { content: "停止した本文" } }),
  ).next!;
  const late = reduceThreadRealtime(
    cancelled,
    event("response.completed", {
      thread_revision: cancelled.revision,
      data: { content: "遅れて届いた完了本文" },
    }),
  );

  assert.equal(late.next, cancelled);
  assert.equal(late.next?.latest_response?.status, "cancelled");
  assert.equal(late.shouldSync, true);
});

test("古い停止HTTP snapshotで次の応答を巻き戻さない", () => {
  const cancelled = reduceThreadRealtime(
    thread,
    event("response.cancelled", { data: { content: "停止した本文" } }),
  ).next!;
  const nextResponse: Thread = {
    ...cancelled,
    revision: cancelled.revision + 1,
    latest_response: {
      ...thread.latest_response!,
      id: "next-request",
      status: "running",
      execution: {
        ...thread.latest_response!.execution,
        id: "next-execution",
        response_request_id: "next-request",
      },
    },
  };

  assert.equal(
    mergeExecutionSnapshot(nextResponse, cancelled, "execution-2"),
    nextResponse,
  );
});
