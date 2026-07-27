import type { BrainState } from "@/lib/human/types";

export function removeCancelledAssignment(
  state: BrainState | undefined,
  claimId: string | undefined,
): BrainState | undefined {
  if (!state || !claimId || state.assignment?.claim_id !== claimId) return state;
  return { ...state, status: "waiting", assignment: null };
}
