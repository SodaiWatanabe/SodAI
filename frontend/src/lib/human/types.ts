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
  draft_content: string;
  draft_revision: number;
  context: HumanContextEntry[];
};

export type HumanAnswerConditions = {
  answerer_ids: string[];
  reasoning_efforts: ReasoningEffort[];
};

export type BrainState = {
  status: "idle" | "waiting" | "assigned";
  rank_name: string;
  assignment: HumanAssignment | null;
  answer_conditions: HumanAnswerConditions;
  available_answerer_ids: string[];
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
