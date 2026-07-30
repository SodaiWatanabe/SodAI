import assert from "node:assert/strict";
import test from "node:test";

import type { Thread, ThreadEntry } from "../../lib/chat/types.ts";
import { displayThreadEntries } from "./thread-display-entries.ts";

const prompt: ThreadEntry = {
  id: "prompt",
  thread_id: "thread",
  author: { id: "user", kind: "human", name: "User" },
  kind: "message",
  content: "考えてください",
  ordinal: 0,
  created_at: "2026-07-16T00:00:00Z",
};

const streaming: Thread = {
  id: "thread",
  space_id: "space",
  title: "会話",
  answerer: "hina",
  revision: 1,
  created_at: "2026-07-16T00:00:00Z",
  updated_at: "2026-07-16T00:00:00Z",
  last_activity_at: "2026-07-16T00:00:00Z",
  entries: [prompt],
  latest_response: {
    id: "request",
    thread_id: "thread",
    input_entry_id: "prompt",
    requested_answerer: "hina",
    reasoning_effort: "none",
    target_actor: { id: "hina", kind: "model", name: "Hina" },
    status: "running",
    created_at: "2026-07-16T00:00:01Z",
    execution: {
      id: "execution",
      response_request_id: "request",
      thread_id: "thread",
      result_entry_id: null,
      answerer: "hina",
      target: "local:hina",
      status: "running",
      attempt_no: 1,
      attempt_id: "attempt",
      partial_output: "考えています",
      resolved_model: "hina@artifact",
      error_code: null,
      created_at: "2026-07-16T00:00:01Z",
    },
  },
};

test("実行中から完了Entryの永続化まで同じ描画keyを維持する", () => {
  const completed: Thread = {
    ...streaming,
    latest_response: {
      ...streaming.latest_response!,
      status: "completed",
      execution: {
        ...streaming.latest_response!.execution,
        result_entry_id: "result",
        status: "completed",
        partial_output: "考えました",
      },
    },
  };
  const persisted: Thread = {
    ...completed,
    entries: [
      prompt,
      {
        id: "result",
        thread_id: "thread",
        author: { id: "hina", kind: "model", name: "Hina" },
        kind: "message",
        content: "考えました",
        ordinal: 1,
        created_at: "2026-07-16T00:00:02Z",
        answerer: "hina",
      },
    ],
  };

  const streamingEntry = displayThreadEntries(streaming).at(-1)!;
  const completedEntry = displayThreadEntries(completed).at(-1)!;
  const persistedEntry = displayThreadEntries(persisted).at(-1)!;

  assert.equal(streamingEntry.id, "execution:execution");
  assert.equal(completedEntry.id, "result");
  assert.equal(persistedEntry.id, "result");
  assert.equal(streamingEntry.renderKey, "execution:execution");
  assert.equal(completedEntry.renderKey, streamingEntry.renderKey);
  assert.equal(persistedEntry.renderKey, streamingEntry.renderKey);
});

test("再実行時は新しい描画keyへ切り替える", () => {
  const retried: Thread = {
    ...streaming,
    latest_response: {
      ...streaming.latest_response!,
      execution: {
        ...streaming.latest_response!.execution,
        id: "execution-retry",
        attempt_no: 2,
        attempt_id: "attempt-retry",
      },
    },
  };

  assert.notEqual(
    displayThreadEntries(retried).at(-1)!.renderKey,
    displayThreadEntries(streaming).at(-1)!.renderKey,
  );
});

test("停止時の部分回答をcancelledとして表示する", () => {
  const cancelled: Thread = {
    ...streaming,
    latest_response: {
      ...streaming.latest_response!,
      status: "cancelled",
      execution: {
        ...streaming.latest_response!.execution,
        status: "cancelled",
        partial_output: "途中までの回答",
      },
    },
  };

  const result = displayThreadEntries(cancelled).at(-1)!;

  assert.equal(result.content, "途中までの回答");
  assert.equal(result.responseStatus, "cancelled");
  assert.equal(result.renderKey, "execution:execution");
});

test("本文がない停止も空のcancelled表示として扱う", () => {
  const cancelled: Thread = {
    ...streaming,
    latest_response: {
      ...streaming.latest_response!,
      status: "cancelled",
      execution: {
        ...streaming.latest_response!.execution,
        status: "cancelled",
        partial_output: "",
      },
    },
  };

  const result = displayThreadEntries(cancelled).at(-1)!;

  assert.equal(result.content, "");
  assert.equal(result.responseStatus, "cancelled");
});

test("Humanの演出本文は確定済み状態を変えずに上書きする", () => {
  const completed: Thread = {
    ...streaming,
    entries: [
      prompt,
      {
        id: "result",
        thread_id: "thread",
        author: { id: "hina", kind: "model", name: "Hina" },
        kind: "message",
        content: "確定済みの回答",
        ordinal: 1,
        created_at: "2026-07-16T00:00:02Z",
        answerer: "human-lite",
        response_status: "completed",
      },
    ],
    latest_response: {
      ...streaming.latest_response!,
      requested_answerer: "human-lite",
      status: "completed",
      execution: {
        ...streaming.latest_response!.execution,
        answerer: "human-lite",
        result_entry_id: "result",
        status: "completed",
        partial_output: "確定済みの回答",
      },
    },
  };

  const result = displayThreadEntries(completed, {
    executionId: "execution",
    content: "確定済み",
  }).at(-1)!;

  assert.equal(result.content, "確定済み");
  assert.equal(result.presenting, true);
  assert.equal(result.responseStatus, "completed");
});
