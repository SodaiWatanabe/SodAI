import type { Actor } from "@/lib/chat/types";

export type HumanContextEntry = {
  author_kind: Actor["kind"];
  content: string;
};

export type HumanAssignment = {
  claim_id: string;
  answerer_name: string;
  context: HumanContextEntry[];
};

export type BrainState = {
  status: "idle" | "waiting" | "assigned";
  rank_name: string;
  assignment: HumanAssignment | null;
};
