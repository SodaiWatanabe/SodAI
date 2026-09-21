import assert from "node:assert/strict";
import { createHash, randomBytes } from "node:crypto";
import test, { after } from "node:test";

import { betterAuth } from "better-auth";
import { memoryAdapter } from "better-auth/adapters/memory";
import { getMigrations } from "better-auth/db/migration";
import { bearer, emailOTP, jwt } from "better-auth/plugins";
import { Pool } from "pg";

import { mobileAuth } from "../src/mobile.js";

const origin = "https://auth.example.test";
const random = () => randomBytes(32).toString("base64url");
const hash = (value: string) => createHash("sha256").update(value).digest("base64url");
const postgresURL = process.env.MOBILE_AUTH_TEST_DATABASE_URL;
if (postgresURL) {
  const url = new URL(postgresURL);
  if (!["localhost", "127.0.0.1"].includes(url.hostname) || url.pathname !== "/sodai_mobile_test") {
    throw new Error("Mobile auth tests require a dedicated loopback sodai_mobile_test database.");
  }
}
const pool = postgresURL ? new Pool({ connectionString: postgresURL }) : undefined;
after(async () => { await pool?.end(); });

async function fixture() {
  const database = { user: [], session: [], account: [], verification: [], jwks: [] };
  const auth = betterAuth({
    baseURL: origin,
    secret: "test-only-secret-with-more-than-thirty-two-characters",
    database: pool ?? memoryAdapter(database),
    socialProviders: { google: { clientId: "test-client", clientSecret: "test-secret" } },
    session: { deferSessionRefresh: true },
    plugins: [
      bearer(),
      mobileAuth(),
      emailOTP({ sendVerificationOTP: async () => undefined }),
      jwt(),
    ],
    logger: { level: "error" },
  });
  if (pool) await (await getMigrations(auth.options)).runMigrations();
  const context = await auth.$context;
  const google = context.socialProviders.find((provider) => provider.id === "google");
  assert.ok(google);
  // Only Google's external network is replaced. Better Auth's callback, state,
  // session creation and the complete native handoff execute normally.
  google.validateAuthorizationCode = async () => ({ accessToken: "test-google-token" });
  google.getUserInfo = async () => ({
    user: { id: "google-test-user", name: "SodAI Tester", email: "tester@example.test", emailVerified: true },
    data: {},
  });
  const cookies = new Map<string, string>();
  async function request(path: string, body?: object, authorization?: string) {
    const headers = new Headers();
    if (cookies.size) headers.set("Cookie", [...cookies].map(([k, v]) => k + "=" + v).join("; "));
    if (authorization) headers.set("Authorization", "Bearer " + authorization);
    if (body) {
      headers.set("Content-Type", "application/json");
      headers.set("Origin", origin);
    }
    const response = await auth.handler(new Request(
      path.startsWith("https:") ? path : origin + "/api/auth" + path,
      { method: body ? "POST" : "GET", headers, ...(body ? { body: JSON.stringify(body) } : {}) },
    ));
    for (const header of response.headers.getSetCookie()) {
      const [pair] = header.split(";");
      const index = pair!.indexOf("=");
      cookies.set(pair!.slice(0, index), pair!.slice(index + 1));
    }
    return response;
  }
  async function login() {
    const verifier = random();
    const state = random();
    const start = await request("/mobile/start?state=" + state + "&code_challenge=" + hash(verifier));
    assert.equal(start.status, 302, await start.clone().text());
    const googleURL = new URL(start.headers.get("location")!);
    assert.equal(googleURL.hostname, "accounts.google.com");
    const oauthState = googleURL.searchParams.get("state")!;
    const callback = await request("/callback/google?code=test-code&state=" + oauthState);
    assert.equal(callback.status, 302, await callback.clone().text());
    const handoff = await request(callback.headers.get("location")!);
    assert.equal(handoff.status, 302, await handoff.clone().text());
    // Explicitly clear any fragment inherited from the provider's browser page.
    assert.ok(handoff.headers.get("location")!.endsWith("#"));
    const appURL = new URL(handoff.headers.get("location")!);
    assert.equal(appURL.origin, "null");
    assert.equal(appURL.protocol, "me.sodai.app:");
    assert.equal(appURL.host, "auth");
    assert.equal(appURL.pathname, "/callback");
    assert.equal(appURL.searchParams.get("state"), state);
    assert.equal(appURL.searchParams.has("token"), false);
    const code = appURL.searchParams.get("code")!;
    assert.ok(code);
    return { code, state, code_verifier: verifier };
  }
  return { auth, context, database, cookies, request, login };
}

test("Google callback -> PKCE exchange -> native session -> JWT -> logout", async () => {
  const f = await fixture();
  const grant = await f.login();
  const exchange = await f.request("/mobile/exchange", grant);
  assert.equal(exchange.status, 200, await exchange.clone().text());
  const result = await exchange.json();
  assert.equal(result.user.email, "tester@example.test");
  assert.ok(result.token);
  const browserSession = await f.request("/get-session");
  const browserToken = (await browserSession.json()).session.token;
  assert.notEqual(result.token, browserToken);
  f.cookies.clear(); // Native process has no browser cookie jar.
  const restored = await f.request("/get-session", {}, result.token);
  assert.equal(restored.status, 200, await restored.clone().text());
  assert.equal((await restored.json()).user.email, "tester@example.test");
  f.cookies.clear();
  const token = await f.request("/token", undefined, result.token);
  assert.equal(token.status, 200, await token.clone().text());
  assert.equal((await token.json()).token.split(".").length, 3);
  const logout = await f.request("/sign-out", {}, result.token);
  assert.equal(logout.status, 200);
  f.cookies.clear();
  assert.equal(await (await f.request("/get-session", {}, result.token)).json(), null);
  f.cookies.clear();
  assert.equal((await (await f.request("/get-session", {}, browserToken)).json()).user.email, "tester@example.test");
});

test("wrong PKCE/state is rejected; valid code is consumed once even concurrently", async () => {
  const f = await fixture();
  const grant = await f.login();
  assert.equal((await f.request("/mobile/exchange", { ...grant, code_verifier: random() })).status, 400);
  assert.equal((await f.request("/mobile/exchange", { ...grant, state: random() })).status, 400);
  const responses = await Promise.all([
    f.request("/mobile/exchange", grant),
    f.request("/mobile/exchange", grant),
  ]);
  assert.deepEqual(responses.map((r) => r.status).sort(), [200, 400]);
  assert.equal((await f.request("/mobile/exchange", grant)).status, 400);
});

test("native POST session check refreshes a due session while GET remains read-only", async () => {
  const f = await fixture();
  const grant = await f.login();
  const result = await (await f.request("/mobile/exchange", grant)).json();
  const oldExpiry = new Date(Date.now() + 24 * 60 * 60 * 1000);
  await f.context.internalAdapter.updateSession(result.token, {
    updatedAt: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000),
    expiresAt: oldExpiry,
  });
  f.cookies.clear();
  const readOnly = await (await f.request("/get-session", undefined, result.token)).json();
  assert.equal(new Date(readOnly.session.expiresAt).getTime(), oldExpiry.getTime());
  f.cookies.clear();
  const refreshed = await (await f.request("/get-session", {}, result.token)).json();
  assert.ok(new Date(refreshed.session.expiresAt).getTime() > oldExpiry.getTime());
});

test("expired handoff and revoked browser session fail closed", async () => {
  const f = await fixture();
  const grant = await f.login();
  await f.context.internalAdapter.deleteVerificationByIdentifier("mobile-code:" + hash(grant.code));
  await f.context.internalAdapter.createVerificationValue({
    identifier: "mobile-code:" + hash(grant.code),
    value: "{}",
    expiresAt: new Date(Date.now() - 1000),
  });
  assert.equal((await f.request("/mobile/exchange", grant)).status, 400);
  const next = await f.login();
  await f.request("/sign-out", {});
  assert.equal((await f.request("/mobile/exchange", next)).status, 401);
});

test("browser binding prevents a callback in a different browser; redirects stay fixed", async () => {
  const f = await fixture();
  const start = await f.request("/mobile/start?state=" + random() + "&code_challenge=" + hash(random()) +
    "&redirect_uri=https://attacker.example");
  const oauthState = new URL(start.headers.get("location")!).searchParams.get("state")!;
  const callback = await f.request("/callback/google?code=test-code&state=" + oauthState);
  const location = callback.headers.get("location")!;
  assert.ok(location.startsWith(origin + "/api/auth/mobile/callback?"));
  for (const key of f.cookies.keys()) if (key.includes("mobile_browser")) f.cookies.delete(key);
  assert.equal((await f.request(location)).status, 400);
});

test("provider cancellation returns state and a generic error without credentials", async () => {
  const f = await fixture();
  const state = random();
  const start = await f.request("/mobile/start?state=" + state + "&code_challenge=" + hash(random()));
  const oauthState = new URL(start.headers.get("location")!).searchParams.get("state")!;
  const callback = await f.request("/callback/google?error=access_denied&state=" + oauthState);
  const handoff = await f.request(callback.headers.get("location")!);
  assert.ok(handoff.headers.get("location")!.endsWith("#"));
  const appURL = new URL(handoff.headers.get("location")!);
  assert.equal(appURL.searchParams.get("state"), state);
  assert.equal(appURL.searchParams.get("error"), "login_failed");
  assert.equal(appURL.searchParams.has("code"), false);
});
