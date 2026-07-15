import type { BetterAuthOptions } from "better-auth";
import { emailOTP, jwt } from "better-auth/plugins";

import { authDatabasePool } from "./database.js";
import {
  getAuthBaseUrl,
  getClientIpAddressHeaders,
  getGoogleCredentials,
  getTrustedOrigins,
  requireEnvironment,
} from "./environment.js";
import { sendSignInOtpEmail } from "./email/index.js";

const authBaseUrl = getAuthBaseUrl();
const googleCredentials = getGoogleCredentials();

export const authCapabilities = Object.freeze({
  google: Boolean(googleCredentials),
});

export const authOptions = {
  appName: "SodAI",
  baseURL: authBaseUrl,
  secret: requireEnvironment("BETTER_AUTH_SECRET"),
  trustedOrigins: getTrustedOrigins(),
  database: authDatabasePool,
  socialProviders: googleCredentials
    ? {
        google: {
          clientId: googleCredentials.clientId,
          clientSecret: googleCredentials.clientSecret,
          prompt: "select_account",
        },
      }
    : {},
  account: {
    accountLinking: {
      enabled: true,
      updateUserInfoOnLink: false,
    },
  },
  session: {
    deferSessionRefresh: true,
    expiresIn: 60 * 60 * 24 * 7,
    updateAge: 60 * 60 * 24,
  },
  rateLimit: {
    enabled: true,
    max: 100,
    storage: "database",
    window: 60,
  },
  advanced: {
    cookiePrefix: "sodai",
    database: {
      generateId: "uuid",
    },
    ipAddress: {
      ipAddressHeaders: getClientIpAddressHeaders(),
    },
  },
  plugins: [
    emailOTP({
      allowedAttempts: 3,
      expiresIn: 5 * 60,
      rateLimit: {
        max: 3,
        window: 60,
      },
      resendStrategy: "rotate",
      sendVerificationOTP: async ({ email, otp, type }) => {
        if (type === "sign-in") await sendSignInOtpEmail(email, otp);
      },
      storeOTP: "hashed",
    }),
    jwt({
      jwt: {
        issuer: authBaseUrl,
        audience: authBaseUrl,
        expirationTime: "10m",
        getSubject: ({ user }) => user.id,
        definePayload: ({ user }) => ({
          email: user.email,
          emailVerified: user.emailVerified,
          name: user.name,
        }),
      },
      jwks: {
        keyPairConfig: {
          alg: "EdDSA",
          crv: "Ed25519",
        },
        rotationInterval: 60 * 60 * 24 * 30,
        gracePeriod: 60 * 60 * 24 * 7,
      },
    }),
  ],
} satisfies BetterAuthOptions;
