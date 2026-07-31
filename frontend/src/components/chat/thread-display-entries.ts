import type { Thread, ThreadEntry } from "@/lib/chat/types";

export type DisplayEntry = ThreadEntry & {
  presenting: boolean;
  renderKey: string;
  responseStatus: "completed" | "streaming" | "failed" | "cancelled";
};

export type ResponsePresentation = {
  content: string;
  executionId: string;
};

function entryRenderKey(entryId: string, thread: Thread) {
  const execution = thread.latest_response?.execution;
  if (
    execution &&
    (entryId === execution.result_entry_id ||
      entryId === `execution:${execution.id}`)
  ) {
    return `execution:${execution.id}`;
  }
  return `entry:${entryId}`;
}

export function displayThreadEntries(
  thread: Thread,
  presentation?: ResponsePresentation,
): DisplayEntry[] {
  const entries: DisplayEntry[] = thread.entries.map((entry) => ({
    ...entry,
    presenting: false,
    renderKey: entryRenderKey(entry.id, thread),
    responseStatus: entry.response_status ?? "completed",
  }));
  const response = thread.latest_response;
  if (!response) return entries;
  const resultIsPersisted = response.execution.result_entry_id
    ? entries.some((entry) => entry.id === response.execution.result_entry_id)
    : false;
  if (
    (response.status === "completed" || response.status === "cancelled") &&
    resultIsPersisted
  ) {
    return applyPresentation(entries, presentation);
  }
  const latestOrdinal = entries.at(-1)?.ordinal ?? -1;
  const entryId =
    response.execution.result_entry_id ?? `execution:${response.execution.id}`;
  entries.push({
    id: entryId,
    thread_id: thread.id,
    author: response.target_actor,
    kind: "message",
    content: response.execution.partial_output,
    ordinal: latestOrdinal + 1,
    created_at: response.created_at,
    answerer: response.requested_answerer,
    execution_id: response.execution.id,
    evaluation: response.execution.evaluation,
    presenting: false,
    renderKey: entryRenderKey(entryId, thread),
    responseStatus:
      response.status === "failed"
        ? "failed"
        : response.status === "cancelled"
          ? "cancelled"
          : response.status === "completed"
            ? "completed"
            : "streaming",
  });
  return applyPresentation(entries, presentation);
}

function applyPresentation(
  entries: DisplayEntry[],
  presentation?: ResponsePresentation,
) {
  if (!presentation) return entries;
  const renderKey = `execution:${presentation.executionId}`;
  return entries.map((entry) =>
    entry.renderKey === renderKey
      ? { ...entry, content: presentation.content, presenting: true }
      : entry,
  );
}
