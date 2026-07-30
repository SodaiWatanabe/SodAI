import type { Actor } from "@/lib/chat/types";
import type { ReasoningEffort } from "@/lib/chat/types";

export type HumanContextEntry = {
  author_kind: Actor["kind"];
  content: string;
};

export type HumanAssignment = {
  claim_id: string;
  answerer_name: string;
  reasoning_effort: ReasoningEffort;
  deadline_at: string;
  context: HumanContextEntry[];
};

export type BrainState = {
  status: "idle" | "waiting" | "assigned";
  rank_name: string;
  assignment: HumanAssignment | null;
};
