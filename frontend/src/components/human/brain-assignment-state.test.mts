import assert from "node:assert/strict";
import test from "node:test";

import type { BrainState } from "../../lib/human/types.ts";
import { removeCancelledAssignment } from "./brain-assignment-state.ts";

const assigned: BrainState = {
  status: "assigned",
  rank_name: "Lite",
  assignment: {
    claim_id: "claim",
    answerer_name: "Human Lite",
    reasoning_effort: "medium",
    deadline_at: "2026-07-30T12:05:00Z",
    context: [],
  },
};

test("取消されたClaimの文脈を再同期前に破棄する", () => {
  assert.deepEqual(removeCancelledAssignment(assigned, "claim"), {
    status: "waiting",
    rank_name: "Lite",
    assignment: null,
  });
});

test("別Claimの取消eventでは現在の割当を保持する", () => {
  assert.equal(removeCancelledAssignment(assigned, "other"), assigned);
});
