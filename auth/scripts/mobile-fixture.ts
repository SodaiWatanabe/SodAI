/**
 * Loopback-only integration fixture. Never imported by src/main.ts.
 * Replaces the external Google network, not SodAI's auth/session/handoff logic.
 */
import { serve } from "@hono/node-server";
import { betterAuth } from "better-auth";
import { memoryAdapter } from "better-auth/adapters/memory";
import { bearer, jwt } from "better-auth/plugins";
import { Hono } from "hono";

import { mobileAuth } from "../src/mobile.js";

const origin = "http://localhost:13209";
const auth = betterAuth({
  baseURL: origin,
  secret: "local-fixture-only-not-a-production-secret-000000",
  database: memoryAdapter({ user: [], session: [], account: [], verification: [], jwks: [] }),
  socialProviders: { google: { clientId: "fixture", clientSecret: "fixture" } },
  session: { deferSessionRefresh: true, expiresIn: 7 * 24 * 60 * 60 },
  plugins: [bearer(), mobileAuth(), jwt()],
  logger: { level: "error" },
});
const context = await auth.$context;
const google = context.socialProviders.find((provider) => provider.id === "google")!;
google.createAuthorizationURL = async ({ state }) => {
  const url = new URL(origin + "/test/consent");
  url.searchParams.set("state", state);
  return url;
};
google.validateAuthorizationCode = async ({ code }) => {
  if (code !== "fixture-consent") return null;
  return { accessToken: "fixture-provider-token" };
};
google.getUserInfo = async () => ({
  user: { id: "fixture-ios-user", email: "ios-test@example.test", name: "SodAI Test", emailVerified: true },
  data: {},
});
const app = new Hono();
app.use("*", async (c, next) => {
  await next();
  // Paths and status only: never log OAuth queries, cookies, or bearer tokens.
  console.info(c.req.method + " " + c.req.path + " " + c.res.status);
});
app.get("/healthz", (c) => c.json({ status: "ok", fixture: true }));
app.get("/api/auth/capabilities", (c) => c.json({ google: true, mobile: true }));
app.get("/test/consent", (c) => {
  const state = c.req.query("state") ?? "";
  if (!/^[A-Za-z0-9_-]+$/.test(state)) return c.text("Invalid state", 400);
  c.header("Cache-Control", "no-store");
  c.header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self' me.sodai.app:; frame-ancestors 'none'");
  return c.html('<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">' +
    '<title>SodAI ローカル検証</title><style>body{font-family:system-ui;padding:40px 24px;line-height:1.8;color:#202124;background:#f5f5f7}' +
    'button{padding:18px;border:0;border-radius:18px;background:#24252b;color:white;font-size:17px;width:100%}p{color:#666}</style>' +
    '<h1>ログインの動作確認</h1><p>これはローカルのテスト画面です。Googleには接続せず、テストアカウントを使用します。</p>' +
    '<form action="/api/auth/callback/google" method="get"><input type="hidden" name="state" value="' + state + '">' +
    '<input type="hidden" name="code" value="fixture-consent"><button type="submit">テストアカウントで続ける</button></form></html>');
});
app.on(["GET", "POST"], "/api/auth/*", (c) => auth.handler(c.req.raw));
const server = serve({ fetch: app.fetch, hostname: "127.0.0.1", port: 13209 });
console.info("SodAI local mobile fixture: " + origin + " (mock Google, in-memory accounts)");
process.once("SIGTERM", () => server.close());
process.once("SIGINT", () => server.close());
