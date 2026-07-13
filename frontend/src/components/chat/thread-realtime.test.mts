import assert from "node:assert/strict";
import test from "node:test";

import type { RealtimeEvent, Thread } from "../../lib/chat/types.ts";
import { reduceThreadRealtime } from "./thread-realtime.ts";

const thread: Thread = {
  id: "thread",
  space_id: "space",
  title: "会話",
  answerer: "hina",
  revision: 3,
  created_at: "2026-07-13T00:00:00Z",
  updated_at: "2026-07-13T00:00:00Z",
  last_activity_at: "2026-07-13T00:00:00Z",
  entries: [],
  latest_response: {
    id: "request",
    thread_id: "thread",
    input_entry_id: "entry",
    requested_answerer: "hina",
    target_actor: { id: "hina", kind: "model", name: "Hina" },
    status: "running",
    created_at: "2026-07-13T00:00:00Z",
    execution: {
      id: "execution-2",
      response_request_id: "request",
      thread_id: "thread",
      result_entry_id: null,
      answerer: "hina",
      target: "local:hina",
      status: "running",
      attempt_no: 2,
      attempt_id: "attempt-2",
      partial_output: "途中",
      resolved_model: "hina@artifact",
      error_code: null,
      created_at: "2026-07-13T00:00:00Z",
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
  assert.equal(decision.shouldSync, true);
});
