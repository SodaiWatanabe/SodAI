import assert from "node:assert/strict";
import test from "node:test";

import type { BrainState } from "../../lib/human/types.ts";
import { removeResolvedAssignment } from "./brain-assignment-state.ts";

const assigned: BrainState = {
  status: "assigned",
  rank_name: "Lite",
  answer_conditions: {
    answerer_ids: ["human-lite"],
    reasoning_efforts: ["low"],
  },
  available_answerer_ids: ["human-lite"],
  assignment: {
    claim_id: "claim",
    answerer_name: "Human Lite",
    reasoning_effort: "medium",
    skip_allowed_until: "2026-07-30T12:00:20Z",
    deadline_at: "2026-07-30T12:05:00Z",
    draft_content: "",
    draft_revision: 0,
    context: [],
  },
};

test("回答済みClaimの文脈を破棄して待機を終了する", () => {
  assert.deepEqual(removeResolvedAssignment(assigned, "claim", "idle"), {
    status: "idle",
    rank_name: "Lite",
    answer_conditions: assigned.answer_conditions,
    available_answerer_ids: assigned.available_answerer_ids,
    assignment: null,
  });
});

test("取消済みClaimの文脈を破棄して待機を継続する", () => {
  assert.deepEqual(removeResolvedAssignment(assigned, "claim", "waiting"), {
    status: "waiting",
    rank_name: "Lite",
    answer_conditions: assigned.answer_conditions,
    available_answerer_ids: assigned.available_answerer_ids,
    assignment: null,
  });
});

test("別Claimの解決eventでは現在の割当を保持する", () => {
  assert.equal(removeResolvedAssignment(assigned, "other", "idle"), assigned);
});
