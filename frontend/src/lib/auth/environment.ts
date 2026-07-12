type ServerEnvironmentName =
  | "AUTH_DATABASE_URL"
  | "BETTER_AUTH_SECRET"
  | "BETTER_AUTH_URL";

export function requireServerEnvironment(name: ServerEnvironmentName): string {
  const value = process.env[name]?.trim();

  if (!value) {
    throw new Error(`${name} is required to start the authentication service.`);
  }

  return value;
}

function parseHttpOrigin(value: string, name: string): string {
  let url: URL;

  try {
    url = new URL(value);
  } catch {
    throw new Error(`${name} must be a valid absolute URL.`);
  }

  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error(`${name} must use http or https.`);
  }

  if (url.pathname !== "/" || url.search || url.hash) {
    throw new Error(`${name} must be an origin without a path, query, or hash.`);
  }

  return url.origin;
}

export function getAuthBaseUrl(): string {
  return parseHttpOrigin(requireServerEnvironment("BETTER_AUTH_URL"), "BETTER_AUTH_URL");
}

export function getTrustedOrigins(): string[] {
  const configuredOrigins = (process.env.BETTER_AUTH_TRUSTED_ORIGINS ?? "")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean)
    .map((origin) => parseHttpOrigin(origin, "BETTER_AUTH_TRUSTED_ORIGINS"));

  return [...new Set([getAuthBaseUrl(), ...configuredOrigins])];
}

export function isGoogleAuthConfigured(): boolean {
  const clientId = process.env.GOOGLE_CLIENT_ID?.trim();
  const clientSecret = process.env.GOOGLE_CLIENT_SECRET?.trim();

  if (Boolean(clientId) !== Boolean(clientSecret)) {
    throw new Error(
      "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must either both be set or both be omitted.",
    );
  }

  return Boolean(clientId && clientSecret);
}

export function getGoogleCredentials():
  | { clientId: string; clientSecret: string }
  | undefined {
  if (!isGoogleAuthConfigured()) {
    return undefined;
  }

  return {
    clientId: process.env.GOOGLE_CLIENT_ID!.trim(),
    clientSecret: process.env.GOOGLE_CLIENT_SECRET!.trim(),
  };
}

export function shouldTrustCloudflareIpHeader(): boolean {
  return process.env.AUTH_TRUST_CLOUDFLARE === "true";
}
