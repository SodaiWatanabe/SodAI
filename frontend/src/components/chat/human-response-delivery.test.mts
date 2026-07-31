import assert from "node:assert/strict";
import test from "node:test";

import type { RealtimeEvent, Thread } from "../../lib/chat/types.ts";
import {
  createHumanResponseDeliveryPlan,
  isLiveHumanResponseCompletion,
} from "./human-response-delivery.ts";

const thread: Thread = {
  id: "thread",
  space_id: "space",
  title: "会話",
  answerer: "human-lite",
  revision: 3,
  created_at: "2026-07-16T00:00:00Z",
  updated_at: "2026-07-16T00:00:00Z",
  last_activity_at: "2026-07-16T00:00:00Z",
  entries: [],
  latest_response: {
    id: "request",
    thread_id: "thread",
    input_entry_id: "entry",
    requested_answerer: "human-lite",
    reasoning_effort: "medium",
    target_actor: { id: "human-lite", kind: "model", name: "Human Lite" },
    status: "running",
    created_at: "2026-07-16T00:00:00Z",
    execution: {
      id: "execution",
      response_request_id: "request",
      thread_id: "thread",
      result_entry_id: null,
      answerer: "human-lite",
      target: "human:human-lite",
      status: "running",
      attempt_no: 1,
      attempt_id: "attempt",
      partial_output: "",
      resolved_model: null,
      error_code: null,
      created_at: "2026-07-16T00:00:00Z",
      evaluation: null,
    },
  },
};

const completed: RealtimeEvent = {
  id: "event",
  sequence: 1,
  type: "response.completed",
  space_id: "space",
  thread_id: "thread",
  thread_revision: 4,
  response_request_id: "request",
  execution_id: "execution",
  occurred_at: "2026-07-16T00:00:01Z",
  data: {
    target_actor_id: "human-lite",
    result_entry_id: "result",
    content: "Humanからの回答です。",
  },
};

test("Human回答を単調に伸びる累積フレームへ分割する", () => {
  const content = "考えを届けます。👩🏽‍💻\n続きです。";
  const plan = createHumanResponseDeliveryPlan(content);

  assert.ok(plan.frames.length > 1);
  assert.ok(plan.frames.length <= 40);
  assert.equal(plan.frames.at(-1), content);
  for (let index = 1; index < plan.frames.length; index += 1) {
    assert.ok(plan.frames[index].startsWith(plan.frames[index - 1]));
    assert.notEqual(plan.frames[index], plan.frames[index - 1]);
  }
});

test("結合絵文字を途中で分割しない", () => {
  const plan = createHumanResponseDeliveryPlan("👩🏽‍💻A");

  assert.deepEqual(plan.frames, ["👩🏽‍💻", "👩🏽‍💻A"]);
});

test("空の回答には配送フレームを作らない", () => {
  assert.deepEqual(createHumanResponseDeliveryPlan(""), {
    frames: [],
    intervalMs: 0,
  });
});

test("1文字の回答は単一フレームとして即時確定できる", () => {
  const plan = createHumanResponseDeliveryPlan("は");

  assert.deepEqual(plan.frames, ["は"]);
  assert.equal(plan.intervalMs, 0);
});

test("進行中の同じHuman Executionだけを配送対象にする", () => {
  const humans = new Set(["human-lite"]);

  assert.equal(isLiveHumanResponseCompletion(thread, completed, humans), true);
  assert.equal(
    isLiveHumanResponseCompletion(
      thread,
      { ...completed, execution_id: "old-execution" },
      humans,
    ),
    false,
  );
  assert.equal(
    isLiveHumanResponseCompletion(
      {
        ...thread,
        latest_response: thread.latest_response
          ? { ...thread.latest_response, status: "completed" }
          : null,
      },
      completed,
      humans,
    ),
    false,
  );
  assert.equal(
    isLiveHumanResponseCompletion(thread, completed, new Set(["hina"])),
    false,
  );
});
