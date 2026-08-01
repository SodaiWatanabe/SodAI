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
  skip_allowed_until: string;
  deadline_at: string;
  context: HumanContextEntry[];
};

export type BrainState = {
  status: "idle" | "waiting" | "assigned";
  rank_name: string;
  assignment: HumanAssignment | null;
};

export type HumanAnswerSummary = {
  execution_id: string;
  answerer_name: string;
  reasoning_effort: ReasoningEffort;
  prompt_preview: string;
  answered_at: string;
};

export type HumanAnswerList = {
  items: HumanAnswerSummary[];
  next_cursor: string | null;
};

export type HumanAnswerDetail = {
  execution_id: string;
  answerer_name: string;
  reasoning_effort: ReasoningEffort;
  answered_at: string;
  context: HumanContextEntry[];
  answer: string;
};
