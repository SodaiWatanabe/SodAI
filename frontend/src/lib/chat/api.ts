"use client";

import type { ApiAccessTokenSource } from "@/lib/auth/api-client";
import { API_BASE_URL } from "@/lib/api/base-url";
import type {
  AvailableModel,
  Conversation,
  ConversationCreation,
  ConversationSummary,
} from "@/lib/chat/types";

export class ChatApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ChatApiError";
  }
}

export function createChatApi(accessToken: ApiAccessTokenSource) {
  async function apiFetch(path: `/${string}`, init: RequestInit = {}) {
    const token = await accessToken.get();
    const headers = new Headers(init.headers);
    if (token) headers.set("Authorization", `Bearer ${token}`);
    if (init.body) headers.set("Content-Type", "application/json");

    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      credentials: "include",
      headers,
    });
    if (response.status === 401 && token) accessToken.invalidate();
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as {
        detail?: string;
      } | null;
      throw new ChatApiError(
        payload?.detail ?? "SodAI APIへ接続できませんでした。",
        response.status,
      );
    }
    return response;
  }

  async function listConversations(): Promise<ConversationSummary[]> {
    const response = await apiFetch("/api/v1/conversations");
    const payload = (await response.json()) as { items: ConversationSummary[] };
    return payload.items;
  }

  async function listModels(): Promise<AvailableModel[]> {
    const response = await apiFetch("/api/v1/models");
    const payload = (await response.json()) as { items: AvailableModel[] };
    return payload.items;
  }

  async function createConversation(
    input: string,
    model: AvailableModel["id"],
  ): Promise<ConversationCreation> {
    const response = await apiFetch("/api/v1/conversations", {
      method: "POST",
      body: JSON.stringify({ input, model }),
    });
    return (await response.json()) as ConversationCreation;
  }

  async function getConversation(id: string): Promise<Conversation> {
    const response = await apiFetch(`/api/v1/conversations/${id}`);
    return (await response.json()) as Conversation;
  }

  async function updateConversation(
    id: string,
    title: string,
  ): Promise<ConversationSummary> {
    const response = await apiFetch(`/api/v1/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    });
    return (await response.json()) as ConversationSummary;
  }

  async function archiveConversation(id: string): Promise<void> {
    await apiFetch(`/api/v1/conversations/${id}/archive`, {
      method: "POST",
    });
  }

  async function createTurn(
    id: string,
    input: string,
    model: AvailableModel["id"],
  ): Promise<ConversationCreation> {
    const response = await apiFetch(`/api/v1/conversations/${id}/turns`, {
      method: "POST",
      body: JSON.stringify({ input, model }),
    });
    return (await response.json()) as ConversationCreation;
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
    archiveConversation,
    createConversation,
    createRealtimeSocket,
    createTurn,
    getConversation,
    listConversations,
    listModels,
    updateConversation,
  };
}

export type ChatApi = ReturnType<typeof createChatApi>;
