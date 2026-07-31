import type {
  ResponseEvaluationValue,
  Thread,
} from "@/lib/chat/types";

export function responseEvaluation(
  thread: Thread | undefined,
  executionId: string,
): ResponseEvaluationValue | null {
  if (!thread) return null;
  const entry = thread.entries.find(
    (candidate) => candidate.execution_id === executionId,
  );
  if (entry) return entry.evaluation;
  return thread.latest_response?.execution.id === executionId
    ? thread.latest_response.execution.evaluation
    : null;
}

export function nextResponseEvaluation(
  current: ResponseEvaluationValue | null,
  selected: ResponseEvaluationValue,
): ResponseEvaluationValue | null {
  return current === selected ? null : selected;
}

export function withResponseEvaluation(
  thread: Thread,
  executionId: string,
  value: ResponseEvaluationValue | null,
): Thread {
  return {
    ...thread,
    entries: thread.entries.map((entry) =>
      entry.execution_id === executionId
        ? { ...entry, evaluation: value }
        : entry,
    ),
    latest_response:
      thread.latest_response?.execution.id === executionId
        ? {
            ...thread.latest_response,
            execution: {
              ...thread.latest_response.execution,
              evaluation: value,
            },
          }
        : thread.latest_response,
  };
}
