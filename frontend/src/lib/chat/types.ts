export type ConversationSummary = {
  id: string;
  title: string;
  model: string;
  created_at: string;
  updated_at: string;
  last_activity_at: string;
};

export type ChatMessage = {
  id: string;
  conversation_id: string;
  speaker: "sodai" | "partner";
  content: string;
  status: "streaming" | "completed" | "failed";
  ordinal: number;
  created_at: string;
  updated_at: string;
};

export type InferenceRun = {
  id: string;
  conversation_id: string;
  input_message_id: string;
  output_message_id: string;
  requested_model: string;
  resolved_model: string;
  status: "queued" | "running" | "completed" | "failed";
  created_at: string;
};

export type Conversation = ConversationSummary & {
  messages: ChatMessage[];
  active_run: InferenceRun | null;
};

export type ConversationCreation = {
  conversation: Conversation;
  run: InferenceRun;
};

export type AvailableModel = {
  id: "archive" | "flagship";
  name: string;
  description: string;
};

export type RealtimeEvent = {
  id: string;
  sequence: number;
  type:
    | "conversation.created"
    | "message.created"
    | "response.started"
    | "response.delta"
    | "response.completed"
    | "response.failed";
  conversation_id: string;
  run_id: string | null;
  occurred_at: string;
  data: {
    message_id?: string;
    delta?: string;
    content?: string;
    title?: string;
    model?: string;
  };
};
