"use client";

import { authClient } from "./client";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export class AuthenticationRequiredError extends Error {
  constructor() {
    super("A valid SodAI session is required.");
    this.name = "AuthenticationRequiredError";
  }
}

export async function getApiAccessToken(): Promise<string> {
  const { data, error } = await authClient.token();

  if (error || !data?.token) {
    throw new AuthenticationRequiredError();
  }

  return data.token;
}

export async function getOptionalApiAccessToken(): Promise<string | null> {
  const { data: session, error } = await authClient.getSession();
  if (error) {
    throw new AuthenticationRequiredError();
  }
  if (!session) {
    return null;
  }
  return getApiAccessToken();
}

export async function authenticatedApiFetch(
  path: `/${string}`,
  init: RequestInit = {},
): Promise<Response> {
  const token = await getApiAccessToken();
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);

  return fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });
}
