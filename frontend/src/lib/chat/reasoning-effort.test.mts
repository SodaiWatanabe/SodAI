import assert from "node:assert/strict";
import test from "node:test";

import type { AvailableAnswerer } from "./types.ts";
import {
  formatReasoningTimeLimit,
  resolveReasoningEffort,
} from "./reasoning-effort.ts";

const human = {
  id: "human-standard",
  name: "Human Standard",
  description: "幅広い相談に対応。",
  kind: "human",
  is_default: false,
  is_legacy: false,
  reasoning_efforts: [
    {
      id: "low",
      name: "軽い",
      execution_time_limit_seconds: 120,
      customer_charge: 500_000,
      performer_reward: 450_000,
    },
    {
      id: "medium",
      name: "中程度",
      execution_time_limit_seconds: 300,
      customer_charge: 1_500_000,
      performer_reward: 1_350_000,
    },
    {
      id: "high",
      name: "深い",
      execution_time_limit_seconds: 600,
      customer_charge: 3_000_000,
      performer_reward: 2_700_000,
    },
  ],
  default_reasoning_effort: "medium",
  pricing: {
    kind: "free",
    asset_code: "sodai-credit",
    scale: 1_000_000,
    tariff_revision: "free-v1",
    fixed_charge: 0,
    input_token_rate: 0,
    output_token_rate: 0,
    maximum_charge: 0,
    unmetered_charge: 0,
  },
} satisfies AvailableAnswerer;

test("Humanの未対応値noneは既定のmediumへ解決する", () => {
  assert.equal(resolveReasoningEffort(human, "none"), "medium");
});

test("Human Standardで未開放の非常に深いは既定値へ解決する", () => {
  assert.equal(resolveReasoningEffort(human, "xhigh"), "medium");
});

test("思考時間の上限を分または時間単位で表示する", () => {
  assert.equal(formatReasoningTimeLimit(120), "最大2分間");
  assert.equal(formatReasoningTimeLimit(1200), "最大20分間");
  assert.equal(formatReasoningTimeLimit(3600), "最大1時間");
});
