import assert from "node:assert/strict";
import test from "node:test";

import { createAuthServiceApp } from "../src/app.js";

test("health, readiness, and capabilities stay outside the Better Auth handler", async () => {
  let forwarded = 0;
  const app = createAuthServiceApp({
    authHandler: () => {
      forwarded += 1;
      return Response.json({ forwarded: true });
    },
    capabilities: { google: true },
    readiness: async () => undefined,
  });

  const health = await app.request("/healthz");
  assert.equal(health.status, 200);
  assert.deepEqual(await health.json(), { status: "ok" });

  const readiness = await app.request("/readyz");
  assert.equal(readiness.status, 200);
  assert.deepEqual(await readiness.json(), { status: "ready" });

  const capabilities = await app.request("/api/auth/capabilities");
  assert.equal(capabilities.status, 200);
  assert.equal(capabilities.headers.get("cache-control"), "no-store");
  assert.deepEqual(await capabilities.json(), { google: true });
  assert.equal(forwarded, 0);
});

test("readiness fails closed when a dependency is unavailable", async () => {
  const app = createAuthServiceApp({
    authHandler: () => Response.json({ forwarded: true }),
    capabilities: { google: false },
    readiness: async () => {
      throw new Error("database unavailable");
    },
  });

  const response = await app.request("/readyz");
  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { status: "unavailable" });
});

test("GET and POST auth requests are delegated without widening the method surface", async () => {
  const requests: Array<{
    body: unknown;
    method: string;
    pathname: string;
    remoteAddress: string | null;
  }> = [];
  const app = createAuthServiceApp({
    authHandler: async (request) => {
      const url = new URL(request.url);
      requests.push({
        body: request.method === "POST" ? await request.json() : null,
        method: request.method,
        pathname: url.pathname,
        remoteAddress: request.headers.get("x-sodai-remote-address"),
      });
      return Response.json({ ok: true });
    },
    capabilities: { google: false },
    remoteAddress: () => "127.0.0.1",
  });

  assert.equal((await app.request("/api/auth/get-session")).status, 200);
  assert.equal(
    (
      await app.request("/api/auth/sign-in/email-otp", {
        body: JSON.stringify({ email: "test@example.com" }),
        headers: { "x-sodai-remote-address": "spoofed" },
        method: "POST",
      })
    ).status,
    200,
  );
  assert.equal(
    (
      await app.request("/api/auth/get-session", {
        method: "PUT",
      })
    ).status,
    404,
  );
  assert.deepEqual(requests, [
    {
      body: null,
      method: "GET",
      pathname: "/api/auth/get-session",
      remoteAddress: "127.0.0.1",
    },
    {
      body: { email: "test@example.com" },
      method: "POST",
      pathname: "/api/auth/sign-in/email-otp",
      remoteAddress: "127.0.0.1",
    },
  ]);
});
