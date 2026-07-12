import type { BetterAuthOptions } from "better-auth";
import { jwt } from "better-auth/plugins";

import { authDatabasePool } from "./database";
import {
  getAuthBaseUrl,
  getGoogleCredentials,
  getTrustedOrigins,
  requireServerEnvironment,
  shouldTrustCloudflareIpHeader,
} from "./environment";
import { sendPasswordResetEmail, sendVerificationEmail } from "./email";

const authBaseUrl = getAuthBaseUrl();
const googleCredentials = getGoogleCredentials();

export const authOptions = {
  appName: "SodAI",
  baseURL: authBaseUrl,
  secret: requireServerEnvironment("BETTER_AUTH_SECRET"),
  trustedOrigins: getTrustedOrigins(),
  database: authDatabasePool,
  emailAndPassword: {
    enabled: true,
    requireEmailVerification: true,
    minPasswordLength: 12,
    maxPasswordLength: 128,
    revokeSessionsOnPasswordReset: true,
    sendResetPassword: async ({ user, url }) => {
      sendPasswordResetEmail(user.email, url);
    },
  },
  emailVerification: {
    autoSignInAfterVerification: true,
    expiresIn: 60 * 60,
    sendOnSignIn: true,
    sendOnSignUp: true,
    sendVerificationEmail: async ({ user, url }) => {
      sendVerificationEmail(user.email, url);
    },
  },
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
    ...(shouldTrustCloudflareIpHeader()
      ? {
          ipAddress: {
            ipAddressHeaders: ["cf-connecting-ip"],
          },
        }
      : {}),
  },
  plugins: [
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
