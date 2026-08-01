"use client";

import type { ApiAccessTokenSource } from "@/lib/auth/api-client";
import { createApiFetch } from "@/lib/api/api-fetch";
import type {
  BrainState,
  HumanAnswerDetail,
  HumanAnswerList,
} from "@/lib/human/types";

export function createHumanApi(accessToken: ApiAccessTokenSource) {
  const apiFetch = createApiFetch(accessToken);

  async function state(): Promise<BrainState> {
    const response = await apiFetch("/api/v1/human/state");
    return (await response.json()) as BrainState;
  }

  async function ready(): Promise<BrainState> {
    const response = await apiFetch("/api/v1/human/readiness", {
      method: "PUT",
    });
    return (await response.json()) as BrainState;
  }

  async function stop(): Promise<BrainState> {
    const response = await apiFetch("/api/v1/human/readiness", {
      method: "DELETE",
    });
    return (await response.json()) as BrainState;
  }

  async function skip(claimId: string): Promise<BrainState> {
    const response = await apiFetch(`/api/v1/human/claims/${claimId}/skip`, {
      method: "POST",
    });
    return (await response.json()) as BrainState;
  }

  async function answer(claimId: string, content: string): Promise<BrainState> {
    const response = await apiFetch(`/api/v1/human/claims/${claimId}/answer`, {
      method: "POST",
      body: JSON.stringify({ content }),
    });
    return (await response.json()) as BrainState;
  }

  async function listAnswers(cursor?: string): Promise<HumanAnswerList> {
    const query = new URLSearchParams({ limit: "20" });
    if (cursor) query.set("cursor", cursor);
    const response = await apiFetch(`/api/v1/human/answers?${query}`);
    return (await response.json()) as HumanAnswerList;
  }

  async function getAnswer(executionId: string): Promise<HumanAnswerDetail> {
    const response = await apiFetch(
      `/api/v1/human/answers/${encodeURIComponent(executionId)}`,
    );
    return (await response.json()) as HumanAnswerDetail;
  }

  return { answer, getAnswer, listAnswers, ready, skip, state, stop };
}

export type HumanApi = ReturnType<typeof createHumanApi>;
