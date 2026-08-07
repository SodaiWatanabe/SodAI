import assert from "node:assert/strict";
import test from "node:test";

import type { Thread } from "../../lib/chat/types.ts";
import {
  resolveResponseActivity,
  responseActivityLabel,
} from "./response-activity.ts";

const thread: Thread = {
  id: "thread",
  space_id: "space",
  title: "会話",
  answerer: "asuka-1",
  revision: 1,
  created_at: "2026-08-07T00:00:00Z",
  updated_at: "2026-08-07T00:00:00Z",
  last_activity_at: "2026-08-07T00:00:00Z",
  entries: [],
  latest_response: {
    id: "request",
    thread_id: "thread",
    input_entry_id: "entry",
    requested_answerer: "asuka-1",
    reasoning_effort: "none",
    target_actor: { id: "asuka-1", kind: "model", name: "Asuka 1" },
    status: "running",
    created_at: "2026-08-07T00:00:00Z",
    execution: {
      id: "execution",
      response_request_id: "request",
      thread_id: "thread",
      result_entry_id: null,
      answerer: "asuka-1",
      target: "local:asuka-1",
      status: "running",
      attempt_no: 1,
      attempt_id: "attempt",
      partial_output: "",
      resolved_model: "asuka-1@artifact",
      generation_phase: "thinking",
      error_code: null,
      created_at: "2026-08-07T00:00:00Z",
      evaluation: null,
    },
  },
};

test("実行中モデルのthinking phaseを思考中として表示する", () => {
  assert.equal(resolveResponseActivity(thread, true, false), "thinking");
  assert.equal(responseActivityLabel("thinking"), "思考中");
});

test("回答phaseと応答開始前は通常の待機表示にする", () => {
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
  assert.equal(resolveResponseActivity(answering, true, false), "waiting");
  assert.equal(resolveResponseActivity(undefined, true, false), "waiting");
});

test("終端Executionに残ったphaseを次の応答へ持ち越さない", () => {
  const completed: Thread = {
    ...thread,
    latest_response: {
      ...thread.latest_response!,
      status: "completed",
      execution: {
        ...thread.latest_response!.execution,
        status: "completed",
      },
    },
  };
  assert.equal(resolveResponseActivity(completed, true, false), "waiting");
});

test("Humanは検索中と思考中を従来どおり区別する", () => {
  assert.equal(resolveResponseActivity(undefined, true, true), "searching");
  assert.equal(resolveResponseActivity(thread, true, true), "thinking");
  assert.equal(resolveResponseActivity(thread, false, true), undefined);
});
