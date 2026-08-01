export type ResponseOperation =
  | { kind: "idle" }
  | { kind: "creating" }
  | { kind: "regenerating"; responseRequestId: string }
  | { kind: "waiting-for-execution-to-cancel" }
  | { kind: "cancelling"; executionId: string };

export const IDLE_RESPONSE_OPERATION: ResponseOperation = { kind: "idle" };

export function requestResponseCancellation(
  operation: ResponseOperation,
  executionId?: string,
): ResponseOperation {
  if (operation.kind === "cancelling") return operation;
  if (executionId) return { kind: "cancelling", executionId };
  if (operation.kind === "creating" || operation.kind === "regenerating") {
    return { kind: "waiting-for-execution-to-cancel" };
  }
  return operation;
}

export function resolveCreatedExecution(
  operation: ResponseOperation,
  executionId: string,
): ResponseOperation {
  if (operation.kind === "cancelling") return operation;
  return operation.kind === "waiting-for-execution-to-cancel"
    ? { kind: "cancelling", executionId }
    : IDLE_RESPONSE_OPERATION;
}

export function resolveTerminalExecution(
  operation: ResponseOperation,
  executionId: string | null,
): ResponseOperation {
  return operation.kind === "cancelling" &&
    operation.executionId === executionId
    ? IDLE_RESPONSE_OPERATION
    : operation;
}

export function responseOperationIsPending(operation: ResponseOperation) {
  return (
    operation.kind === "waiting-for-execution-to-cancel" ||
    operation.kind === "cancelling"
  );
}
