import type { RealtimeEvent, Thread } from "@/lib/chat/types";

const RESPONSE_EVENT_TYPES = new Set<RealtimeEvent["type"]>([
  "response.queued",
  "response.started",
  "response.delta",
  "response.completed",
  "response.failed",
  "response.cancelled",
]);

export type ThreadRealtimeDecision = {
  handled: boolean;
  next: Thread | undefined;
  shouldSync: boolean;
};

export function mergeExecutionSnapshot(
  current: Thread | undefined,
  incoming: Thread,
  executionId: string,
): Thread {
  if (!current) return incoming;
  if (current.id !== incoming.id || incoming.revision < current.revision) {
    return current;
  }
  if (incoming.revision > current.revision) return incoming;
  return incoming.latest_response?.execution.id === executionId &&
    current.latest_response?.execution.id === executionId
    ? incoming
    : current;
}

export function reduceThreadRealtime(
  current: Thread | undefined,
  event: RealtimeEvent,
): ThreadRealtimeDecision {
  if (!RESPONSE_EVENT_TYPES.has(event.type)) {
    return { handled: false, next: current, shouldSync: false };
  }
  if (event.type === "response.queued") {
    return { handled: true, next: current, shouldSync: true };
  }

  const response = current?.latest_response;
  if (
    !current ||
    !response ||
    response.id !== event.response_request_id ||
    response.execution.id !== event.execution_id
  ) {
    return { handled: true, next: current, shouldSync: true };
  }
  if (event.thread_revision < current.revision) {
    return { handled: true, next: current, shouldSync: false };
  }

  const currentIsTerminal = ["completed", "failed", "cancelled"].includes(
    response.status,
  );
  if (currentIsTerminal) {
    return { handled: true, next: current, shouldSync: true };
  }

  const terminal =
    event.type === "response.completed" ||
    event.type === "response.failed" ||
    event.type === "response.cancelled";
  const status =
    event.type === "response.completed"
      ? "completed"
      : event.type === "response.failed"
        ? "failed"
        : event.type === "response.cancelled"
          ? "cancelled"
        : "running";
  return {
    handled: true,
    shouldSync: terminal,
    next: {
      ...current,
      revision: event.thread_revision,
      latest_response: {
        ...response,
        status,
        execution: {
          ...response.execution,
          status,
          partial_output: event.data.content ?? response.execution.partial_output,
          resolved_model:
            event.data.resolved_model ?? response.execution.resolved_model,
          result_entry_id:
            event.data.result_entry_id ?? response.execution.result_entry_id,
          error_code: event.data.error_code ?? response.execution.error_code,
        },
      },
    },
  };
}
