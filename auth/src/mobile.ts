import { createHash, randomBytes, timingSafeEqual } from "node:crypto";

import type { BetterAuthPlugin } from "better-auth";
import { createAuthEndpoint, getSessionFromCtx, signInSocial } from "better-auth/api";
import * as z from "zod";

const CALLBACK = "me.sodai.app://auth/callback";
const TRANSACTION_SECONDS = 10 * 60;
const CODE_SECONDS = 60;
const randomValue = () => randomBytes(32).toString("base64url");
const digest = (value: string) => createHash("sha256").update(value).digest("base64url");
const safeEqual = (a: string, b: string) => {
  const left = Buffer.from(a);
  const right = Buffer.from(b);
  return left.length === right.length && timingSafeEqual(left, right);
};
const opaque = z.string().regex(/^[A-Za-z0-9_-]{43}$/);
const transactionSchema = z.object({
  state: opaque,
  challenge: opaque,
  browser: opaque,
});
const grantSchema = z.object({
  state: opaque,
  challenge: opaque,
  sessionToken: z.string().min(1),
});

/**
 * Browser -> native handoff. Google OAuth remains owned by Better Auth.
 * Only a short-lived, PKCE-bound code crosses the fixed app callback URL.
 * Verification records use the existing auth schema and atomic consumption.
 */
export function mobileAuth(): BetterAuthPlugin {
  return {
    id: "sodai-mobile",
    rateLimit: [
      { pathMatcher: (path) => path.startsWith("/mobile/"), window: 60, max: 20 },
    ],
    endpoints: {
      mobileStart: createAuthEndpoint("/mobile/start", {
        method: "GET",
        query: z.object({ state: opaque, code_challenge: opaque }),
      }, async (ctx) => {
        ctx.setHeader("Cache-Control", "no-store");
        ctx.setHeader("Referrer-Policy", "no-referrer");
        const request = randomValue();
        const browser = randomValue();
        const cookie = ctx.context.createAuthCookie("mobile_browser", {
          maxAge: TRANSACTION_SECONDS,
          sameSite: "lax",
          httpOnly: true,
          path: "/api/auth/mobile",
        });
        await ctx.context.internalAdapter.createVerificationValue({
          identifier: "mobile-request:" + digest(request),
          value: JSON.stringify({
            state: ctx.query.state,
            challenge: ctx.query.code_challenge,
            browser: digest(browser),
          }),
          expiresAt: new Date(Date.now() + TRANSACTION_SECONDS * 1000),
        });
        const callback = ctx.context.baseURL + "/mobile/callback?request=" + request;
        // Calling the library's endpoint retains Google's own state/PKCE handling.
        const result = await signInSocial()({
          context: ctx.context,
          headers: ctx.headers ?? new Headers(),
          method: "POST",
          body: {
            provider: "google",
            callbackURL: callback,
            newUserCallbackURL: callback,
            errorCallbackURL: callback,
            disableRedirect: true,
          },
          returnHeaders: true,
          asResponse: false,
        });
        for (const value of result.headers.getSetCookie()) {
          ctx.responseHeaders.append("set-cookie", value);
        }
        await ctx.setSignedCookie(cookie.name, browser, ctx.context.secret, cookie.attributes);
        if (!result.response.url) {
          throw ctx.error("BAD_REQUEST", { message: "Google login is unavailable." });
        }
        throw ctx.redirect(result.response.url);
      }),
      mobileCallback: createAuthEndpoint("/mobile/callback", {
        method: "GET",
        query: z.object({
          request: opaque,
          error: z.string().optional(),
          error_description: z.string().optional(),
        }),
      }, async (ctx) => {
        ctx.setHeader("Cache-Control", "no-store");
        ctx.setHeader("Referrer-Policy", "no-referrer");
        const identifier = "mobile-request:" + digest(ctx.query.request);
        const record = await ctx.context.internalAdapter.findVerificationValue(identifier);
        const transaction = record && transactionSchema.safeParse(JSON.parse(record.value));
        const cookie = ctx.context.createAuthCookie("mobile_browser", {
          path: "/api/auth/mobile",
        });
        const browser = await ctx.getSignedCookie(cookie.name, ctx.context.secret);
        if (!record || record.expiresAt <= new Date() || !transaction?.success ||
            !browser || !safeEqual(transaction.data.browser, digest(browser))) {
          throw ctx.error("BAD_REQUEST", { message: "Invalid or expired login request." });
        }
        if (!await ctx.context.internalAdapter.consumeVerificationValue(identifier)) {
          throw ctx.error("BAD_REQUEST", { message: "Login request already used." });
        }
        ctx.setCookie(cookie.name, "", { ...cookie.attributes, maxAge: 0 });
        const callback = new URL(CALLBACK);
        callback.searchParams.set("state", transaction.data.state);
        const session = ctx.query.error ? null : await getSessionFromCtx(ctx);
        if (!session) {
          callback.searchParams.set("error", "login_failed");
          throw ctx.redirect(callback.toString());
        }
        const code = randomValue();
        await ctx.context.internalAdapter.createVerificationValue({
          identifier: "mobile-code:" + digest(code),
          value: JSON.stringify({
            state: transaction.data.state,
            challenge: transaction.data.challenge,
            sessionToken: session.session.token,
          }),
          expiresAt: new Date(Date.now() + CODE_SECONDS * 1000),
        });
        callback.searchParams.set("code", code);
        throw ctx.redirect(callback.toString());
      }),
      mobileExchange: createAuthEndpoint("/mobile/exchange", {
        method: "POST",
        body: z.object({
          code: opaque,
          state: opaque,
          code_verifier: z.string().regex(/^[A-Za-z0-9._~-]{43,128}$/),
        }),
      }, async (ctx) => {
        ctx.setHeader("Cache-Control", "no-store");
        const identifier = "mobile-code:" + digest(ctx.body.code);
        const record = await ctx.context.internalAdapter.findVerificationValue(identifier);
        const grant = record && grantSchema.safeParse(JSON.parse(record.value));
        if (!record || record.expiresAt <= new Date() || !grant?.success ||
            !safeEqual(grant.data.challenge, digest(ctx.body.code_verifier)) ||
            !safeEqual(grant.data.state, ctx.body.state)) {
          throw ctx.error("BAD_REQUEST", { message: "Invalid or expired login code." });
        }
        if (!await ctx.context.internalAdapter.consumeVerificationValue(identifier)) {
          throw ctx.error("BAD_REQUEST", { message: "Login code already used." });
        }
        const browserSession = await ctx.context.internalAdapter.findSession(grant.data.sessionToken);
        if (!browserSession || browserSession.session.expiresAt <= new Date()) {
          throw ctx.error("UNAUTHORIZED", { message: "Browser session expired." });
        }
        // A separate session makes logging out of this phone independent of the browser.
        const session = await ctx.context.internalAdapter.createSession(browserSession.user.id);
        if (!session) throw ctx.error("INTERNAL_SERVER_ERROR", { message: "Session creation failed." });
        return ctx.json({
          token: session.token,
          expiresAt: session.expiresAt.toISOString(),
          user: {
            id: browserSession.user.id,
            name: browserSession.user.name,
            email: browserSession.user.email,
          },
        });
      }),
    },
  };
}
