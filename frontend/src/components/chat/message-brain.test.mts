import assert from "node:assert/strict";
import test from "node:test";

import type {
  AvailableAnswerer,
  ThreadEntry,
} from "../../lib/chat/types.ts";
import { resolveMessageBrain } from "./message-brain.ts";

const entry: ThreadEntry = {
  id: "entry",
  thread_id: "thread",
  author: { id: "actor", kind: "model", name: "モデル" },
  kind: "message",
  content: "回答です。",
  ordinal: 1,
  created_at: "2026-07-16T00:00:00Z",
  answerer: "asuka-1",
};

const answerer = {
  id: "asuka-1",
  name: "Asuka 1",
  description: "会話に最適。",
  kind: "ai",
  is_default: true,
  is_legacy: false,
  reasoning_efforts: [
    {
      id: "none",
      name: "なし",
      execution_time_limit_seconds: null,
      customer_charge: 0,
      performer_reward: 0,
    },
  ],
  default_reasoning_effort: "none",
  pricing: {
    kind: "free",
    asset_code: "sodai-credit",
    scale: 1_000_000,
    tariff_revision: "test",
    fixed_charge: 0,
    input_token_rate: 0,
    output_token_rate: 0,
    maximum_charge: 0,
    unmetered_charge: 0,
  },
} satisfies AvailableAnswerer;

test("履歴EntryのAnswererを表示名へ変換する", () => {
  assert.deepEqual(resolveMessageBrain(entry, [answerer]), {
    name: "Asuka 1",
  });
});

test("Answererがカタログにない場合は作者名へ戻す", () => {
  assert.deepEqual(
    resolveMessageBrain(
      { ...entry, answerer: null },
      [],
    ),
    { name: "モデル" },
  );
});

test("Human回答もAnswererの表示名へ変換する", () => {
  const humanAnswerer = {
    ...answerer,
    id: "human-lite",
    name: "Human Lite",
    kind: "human",
  } satisfies AvailableAnswerer;

  assert.deepEqual(
    resolveMessageBrain(
      {
        ...entry,
        author: { ...entry.author, kind: "human", name: "Human" },
        answerer: "human-lite",
      },
      [humanAnswerer],
    ),
    { name: "Human Lite" },
  );
});
