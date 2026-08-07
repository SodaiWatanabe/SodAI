import assert from "node:assert/strict";
import test from "node:test";

import type { Thread } from "./types.ts";
import {
  nextResponseEvaluation,
  responseEvaluation,
  withResponseEvaluation,
} from "./response-evaluation.ts";

const thread: Thread = {
  id: "thread",
  space_id: "space",
  title: "評価",
  answerer: "hina",
  revision: 1,
  created_at: "2026-07-31T00:00:00Z",
  updated_at: "2026-07-31T00:00:00Z",
  last_activity_at: "2026-07-31T00:00:00Z",
  entries: [
    {
      id: "result",
      thread_id: "thread",
      author: { id: "hina", kind: "model", name: "Hina" },
      kind: "message",
      content: "回答",
      ordinal: 1,
      created_at: "2026-07-31T00:00:01Z",
      answerer: "hina",
      response_status: "completed",
      execution_id: "execution",
      evaluation: null,
    },
  ],
  latest_response: {
    id: "request",
    thread_id: "thread",
    input_entry_id: "prompt",
    requested_answerer: "hina",
    reasoning_effort: "none",
    target_actor: { id: "hina", kind: "model", name: "Hina" },
    status: "completed",
    created_at: "2026-07-31T00:00:00Z",
    execution: {
      id: "execution",
      response_request_id: "request",
      thread_id: "thread",
      result_entry_id: "result",
      answerer: "hina",
      target: "local:hina",
      status: "completed",
      attempt_no: 1,
      attempt_id: "attempt",
      partial_output: "回答",
      resolved_model: "hina@test",
      generation_phase: null,
      error_code: null,
      created_at: "2026-07-31T00:00:00Z",
      evaluation: null,
    },
  },
};

test("評価は永続Entryと最新Executionへ同時に反映する", () => {
  const updated = withResponseEvaluation(thread, "execution", "positive");

  assert.equal(responseEvaluation(updated, "execution"), "positive");
  assert.equal(updated.entries[0].evaluation, "positive");
  assert.equal(updated.latest_response?.execution.evaluation, "positive");
  assert.equal(thread.entries[0].evaluation, null);
});

test("評価を取り消すと両方の投影が未評価へ戻る", () => {
  const evaluated = withResponseEvaluation(thread, "execution", "negative");
  const cleared = withResponseEvaluation(evaluated, "execution", null);

  assert.equal(responseEvaluation(cleared, "execution"), null);
  assert.equal(cleared.entries[0].evaluation, null);
  assert.equal(cleared.latest_response?.execution.evaluation, null);
});

test("同じ評価をもう一度選ぶと解除し、別の評価なら切り替える", () => {
  assert.equal(nextResponseEvaluation(null, "positive"), "positive");
  assert.equal(nextResponseEvaluation("positive", "positive"), null);
  assert.equal(
    nextResponseEvaluation("positive", "negative"),
    "negative",
  );
});
