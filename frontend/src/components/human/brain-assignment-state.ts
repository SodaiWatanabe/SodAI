import type { BrainState } from "@/lib/human/types";

export function removeResolvedAssignment(
  state: BrainState | undefined,
  claimId: string | undefined,
  status: "idle" | "waiting",
): BrainState | undefined {
  if (!state || !claimId || state.assignment?.claim_id !== claimId) return state;
  return { ...state, status, assignment: null };
}
