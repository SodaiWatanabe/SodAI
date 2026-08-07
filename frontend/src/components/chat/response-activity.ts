import type { Thread } from "@/lib/chat/types";

export type ResponseActivity = "searching" | "thinking" | "waiting";

export function resolveResponseActivity(
  thread: Thread | undefined,
  responding: boolean,
  humanResponse: boolean,
): ResponseActivity | undefined {
  if (!responding) return undefined;
  const response = thread?.latest_response;
  if (humanResponse) {
    return response?.status === "running" ? "thinking" : "searching";
  }
  return response?.status === "running" &&
    response.execution.generation_phase === "thinking"
    ? "thinking"
    : "waiting";
}

export function responseActivityLabel(activity: ResponseActivity): string {
  if (activity === "searching") return "利用可能な脳を探しています";
  if (activity === "thinking") return "思考中";
  return "SodAIが応答しています";
}
