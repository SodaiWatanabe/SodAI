import "server-only";

import { cache } from "react";
import { headers } from "next/headers";

import { getAuthServiceUrl } from "./service-url";

const AUTH_REQUEST_TIMEOUT_MS = 3_000;

type CurrentSession = {
  session: Record<string, unknown>;
  user: {
    email: string;
    id: string;
    image?: string | null;
    name: string;
  };
};

type AuthCapabilities = {
  google: boolean;
};

export class AuthServiceUnavailableError extends Error {
  constructor(message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "AuthServiceUnavailableError";
  }
}

export class AuthServiceResponseError extends Error {
  readonly status: number;

  constructor(status: number) {
    super(`The authentication service returned ${status}.`);
    this.name = "AuthServiceResponseError";
    this.status = status;
  }
}

export class AuthServiceProtocolError extends Error {
  constructor(message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "AuthServiceProtocolError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isCurrentSession(value: unknown): value is CurrentSession {
  if (!isRecord(value) || !isRecord(value.user) || !isRecord(value.session)) {
    return false;
  }
  return (
    typeof value.user.id === "string" &&
    typeof value.user.name === "string" &&
    typeof value.user.email === "string" &&
    (value.user.image === undefined ||
      value.user.image === null ||
      typeof value.user.image === "string")
  );
}

async function requestAuth(path: string): Promise<Response> {
  const incomingHeaders = await headers();
  const forwardedHeaders = new Headers();
  for (const name of [
    "cf-connecting-ip",
    "cookie",
    "user-agent",
    "x-forwarded-for",
  ]) {
    const value = incomingHeaders.get(name);
    if (value) forwardedHeaders.set(name, value);
  }

  try {
    return await fetch(`${getAuthServiceUrl()}${path}`, {
      cache: "no-store",
      headers: forwardedHeaders,
      signal: AbortSignal.timeout(AUTH_REQUEST_TIMEOUT_MS),
    });
  } catch (error) {
    throw new AuthServiceUnavailableError(
      "The authentication service could not be reached.",
      { cause: error },
    );
  }
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch (error) {
    throw new AuthServiceProtocolError(
      "The authentication service returned invalid JSON.",
      { cause: error },
    );
  }
}

export const getCurrentSession = cache(async () => {
  const response = await requestAuth("/api/auth/get-session?disableRefresh=true");
  if (!response.ok) {
    throw new AuthServiceResponseError(response.status);
  }

  const payload = await readJson(response);
  if (payload === null) return null;
  if (!isCurrentSession(payload)) {
    throw new AuthServiceProtocolError(
      "The authentication service returned an invalid session response.",
    );
  }
  return payload;
});

export const getCurrentApiAccessToken = cache(async () => {
  const response = await requestAuth("/api/auth/token");
  if (response.status === 401) return null;
  if (!response.ok) {
    throw new AuthServiceResponseError(response.status);
  }

  const payload = await readJson(response);
  if (!isRecord(payload) || typeof payload.token !== "string") {
    throw new AuthServiceProtocolError(
      "The authentication service returned an invalid token response.",
    );
  }
  return payload.token;
});

export const getAuthCapabilities = cache(async (): Promise<AuthCapabilities> => {
  const response = await requestAuth("/api/auth/capabilities");
  if (!response.ok) {
    throw new AuthServiceResponseError(response.status);
  }

  const payload = await readJson(response);
  if (!isRecord(payload) || typeof payload.google !== "boolean") {
    throw new AuthServiceProtocolError(
      "The authentication service returned invalid capabilities.",
    );
  }
  return { google: payload.google };
});
