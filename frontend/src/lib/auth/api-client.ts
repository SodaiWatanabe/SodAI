"use client";

import { authClient } from "./client";

export type ApiAccessTokenSource = {
  get: () => Promise<string | null>;
  invalidate: () => void;
};

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
