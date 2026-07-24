import assert from "node:assert/strict";
import test from "node:test";

import { proxyAuthRequest } from "./proxy.ts";

test("認証リクエストと応答を同一origin proxyで透過する", async () => {
  const responseHeaders = new Headers({ location: "/settings" });
  responseHeaders.append("set-cookie", "session=one; Path=/; HttpOnly");
  responseHeaders.append("set-cookie", "state=two; Path=/; HttpOnly");
  const upstreamResponse = new Response(null, {
    headers: responseHeaders,
    status: 302,
  });
  let forwardedUrl: URL | undefined;
  let forwardedInit: RequestInit | undefined;

  const response = await proxyAuthRequest(
    new Request("https://sodai.example/api/auth/callback/google?code=value", {
      body: JSON.stringify({ accepted: true }),
      headers: {
        "content-type": "application/json",
        host: "sodai.example",
        "x-sodai-remote-address": "spoofed",
      },
      method: "POST",
    }),
    {
      fetch: async (input, init) => {
        forwardedUrl = new URL(input.toString());
        forwardedInit = init;
        return upstreamResponse;
      },
      serviceUrl: "http://auth.internal:13201",
    },
  );

  assert.equal(
    forwardedUrl?.toString(),
    "http://auth.internal:13201/api/auth/callback/google?code=value",
  );
  assert.equal(forwardedInit?.method, "POST");
  assert.equal(forwardedInit?.redirect, "manual");
  const forwardedHeaders = new Headers(forwardedInit?.headers);
  assert.equal(forwardedHeaders.get("content-type"), "application/json");
  assert.equal(forwardedHeaders.has("host"), false);
  assert.equal(forwardedHeaders.has("x-sodai-remote-address"), false);
  assert.equal(await new Response(forwardedInit?.body).text(), '{"accepted":true}');
  assert.strictEqual(response, upstreamResponse);
  assert.deepEqual(response.headers.getSetCookie(), [
    "session=one; Path=/; HttpOnly",
    "state=two; Path=/; HttpOnly",
  ]);
  assert.equal(response.headers.get("location"), "/settings");
});

test("認証サービスへ接続できない場合は機密情報を含めず502を返す", async () => {
  const response = await proxyAuthRequest(
    new Request("https://sodai.example/api/auth/get-session"),
    {
      fetch: async () => {
        throw new Error("private upstream detail");
      },
      serviceUrl: "http://auth.internal:13201",
    },
  );

  assert.equal(response.status, 502);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.deepEqual(await response.json(), {
    code: "AUTH_SERVICE_UNAVAILABLE",
  });
});
