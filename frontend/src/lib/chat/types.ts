export type ThreadSummary = {
  id: string;
  space_id: string;
  title: string;
  answerer: string;
  revision: number;
  created_at: string;
  updated_at: string;
  last_activity_at: string;
};

export type Actor = {
  id: string;
  kind: "human" | "model" | "agent" | "tool" | "system";
  name: string;
};

export type ThreadEntry = {
  id: string;
  thread_id: string;
  author: Actor;
  kind: "message";
  content: string;
  ordinal: number;
  created_at: string;
};

export type Execution = {
  id: string;
  response_request_id: string;
  thread_id: string;
  result_entry_id: string | null;
  answerer: string;
  target: string;
  status: "queued" | "running" | "completed" | "failed";
  attempt_no: number;
  attempt_id: string;
  partial_output: string;
  resolved_model: string | null;
  error_code: string | null;
  created_at: string;
};

export type ResponseRequest = {
  id: string;
  thread_id: string;
  input_entry_id: string;
  requested_answerer: string;
  target_actor: Actor;
  status: "queued" | "running" | "completed" | "failed";
  execution: Execution;
  created_at: string;
};

export type Thread = ThreadSummary & {
  entries: ThreadEntry[];
  latest_response: ResponseRequest | null;
};

export type ThreadSearchHit = {
  thread: ThreadSummary;
  source: "title" | "entry";
  entry_id: string | null;
  snippet: string;
};

export type ThreadSearchPage = {
  items: ThreadSearchHit[];
  has_more: boolean;
};

export type ResponseCreation = {
  thread: Thread;
  response: ResponseRequest;
};

export type AvailableAnswerer = {
  id: string;
  name: string;
  description: string;
  kind: "ai" | "human";
  is_default: boolean;
  is_legacy: boolean;
  pricing: {
    kind: "free" | "metered";
    asset_code: string;
    scale: number;
    tariff_revision: string;
    fixed_charge: number;
    input_token_rate: number;
    output_token_rate: number;
    maximum_charge: number;
    unmetered_charge: number;
  };
};

export type RealtimeEvent = {
  id: string;
  sequence: number;
  type:
    | "thread.created"
    | "thread.updated"
    | "thread.archived"
    | "entry.created"
    | "response.queued"
    | "response.started"
    | "response.delta"
    | "response.completed"
    | "response.failed"
    | "human.assigned"
    | "sync.required";
  space_id: string;
  thread_id: string;
  thread_revision: number;
  response_request_id: string | null;
  execution_id: string | null;
  occurred_at: string;
  data: {
    input_entry_id?: string;
    target_actor_id?: string;
    result_entry_id?: string | null;
    delta?: string;
    content?: string;
    title?: string;
    answerer?: string;
    resolved_model?: string;
    error_code?: string;
    created_at?: string;
    updated_at?: string;
    last_activity_at?: string;
    attempt_no?: number;
    claim_id?: string;
  };
};
