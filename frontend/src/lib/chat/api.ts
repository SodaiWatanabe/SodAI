"use client";

import type { ApiAccessTokenSource } from "@/lib/auth/api-client";
import { API_BASE_URL } from "@/lib/api/base-url";
import { createApiFetch } from "@/lib/api/api-fetch";
import type {
  AvailableAnswerer,
  Execution,
  ReasoningEffort,
  ResponseEvaluation,
  ResponseEvaluationValue,
  ResponseCreation,
  Thread,
  ThreadSearchPage,
  ThreadSummary,
} from "@/lib/chat/types";

export function createChatApi(accessToken: ApiAccessTokenSource) {
  const apiFetch = createApiFetch(accessToken);

  async function listThreads(): Promise<ThreadSummary[]> {
    const response = await apiFetch("/api/v1/threads");
    const payload = (await response.json()) as { items: ThreadSummary[] };
    return payload.items;
  }

  async function listAnswerers(): Promise<AvailableAnswerer[]> {
    const response = await apiFetch("/api/v1/answerers");
    const payload = (await response.json()) as { items: AvailableAnswerer[] };
    return payload.items;
  }

  async function searchThreads(
    query: string,
    limit = 20,
    signal?: AbortSignal,
  ): Promise<ThreadSearchPage> {
    const response = await apiFetch("/api/v1/thread-searches", {
      method: "POST",
      body: JSON.stringify({ query, limit }),
      signal,
    });
    return (await response.json()) as ThreadSearchPage;
  }

  async function createThread(
    input: string,
    answerer: AvailableAnswerer["id"],
    reasoningEffort: ReasoningEffort,
  ): Promise<ResponseCreation> {
    const response = await apiFetch("/api/v1/threads", {
      method: "POST",
      body: JSON.stringify({
        input,
        answerer,
        reasoning_effort: reasoningEffort,
      }),
    });
    return (await response.json()) as ResponseCreation;
  }

  async function getThread(id: string): Promise<Thread> {
    const response = await apiFetch(`/api/v1/threads/${id}`);
    return (await response.json()) as Thread;
  }

  async function updateThread(id: string, title: string): Promise<ThreadSummary> {
    const response = await apiFetch(`/api/v1/threads/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    });
    return (await response.json()) as ThreadSummary;
  }

  async function archiveThread(id: string): Promise<void> {
    await apiFetch(`/api/v1/threads/${id}/archive`, { method: "POST" });
  }

  async function createResponse(
    threadId: string,
    input: string,
    answerer: AvailableAnswerer["id"],
    reasoningEffort: ReasoningEffort,
  ): Promise<ResponseCreation> {
    const response = await apiFetch("/api/v1/response-requests", {
      method: "POST",
      body: JSON.stringify({
        thread_id: threadId,
        input,
        answerer,
        reasoning_effort: reasoningEffort,
      }),
    });
    return (await response.json()) as ResponseCreation;
  }

  async function retryResponse(
    responseRequestId: string,
    idempotencyKey: string,
  ): Promise<Execution> {
    const response = await apiFetch(
      `/api/v1/response-requests/${responseRequestId}/executions`,
      {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
      },
    );
    return (await response.json()) as Execution;
  }

  async function cancelExecution(executionId: string): Promise<Thread> {
    const response = await apiFetch(`/api/v1/executions/${executionId}/cancel`, {
      method: "POST",
    });
    return (await response.json()) as Thread;
  }

  async function setResponseEvaluation(
    executionId: string,
    value: ResponseEvaluationValue,
  ): Promise<ResponseEvaluation> {
    const response = await apiFetch(
      `/api/v1/executions/${executionId}/evaluation`,
      {
        method: "PUT",
        body: JSON.stringify({ value }),
      },
    );
    return (await response.json()) as ResponseEvaluation;
  }

  async function clearResponseEvaluation(executionId: string): Promise<void> {
    await apiFetch(`/api/v1/executions/${executionId}/evaluation`, {
      method: "DELETE",
    });
  }

  async function createRealtimeSocket(after?: number): Promise<WebSocket> {
    const response = await apiFetch("/api/v1/realtime/tickets", {
      method: "POST",
    });
    const { ticket, cursor } = (await response.json()) as {
      ticket: string;
      cursor: number;
    };
    const url = new URL(`${API_BASE_URL}/api/v1/realtime`);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.searchParams.set("ticket", ticket);
    url.searchParams.set("after", String(after ?? cursor));
    return new WebSocket(url);
  }

  return {
    archiveThread,
    cancelExecution,
    clearResponseEvaluation,
    createRealtimeSocket,
    createResponse,
    createThread,
    getThread,
    listAnswerers,
    listThreads,
    retryResponse,
    searchThreads,
    setResponseEvaluation,
    updateThread,
  };
}

export type ChatApi = ReturnType<typeof createChatApi>;
