type RequiredEnvironmentName =
  | "AUTH_DATABASE_URL"
  | "BETTER_AUTH_SECRET"
  | "BETTER_AUTH_URL";

export type GoogleCredentials = {
  clientId: string;
  clientSecret: string;
};

export function requireEnvironment(name: RequiredEnvironmentName): string {
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
  return parseHttpOrigin(requireEnvironment("BETTER_AUTH_URL"), "BETTER_AUTH_URL");
}

export function getTrustedOrigins(): string[] {
  const configuredOrigins = (process.env.BETTER_AUTH_TRUSTED_ORIGINS ?? "")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean)
    .map((origin) => parseHttpOrigin(origin, "BETTER_AUTH_TRUSTED_ORIGINS"));

  return [...new Set([getAuthBaseUrl(), ...configuredOrigins])];
}

export function getGoogleCredentials(): GoogleCredentials | undefined {
  const clientId = process.env.GOOGLE_CLIENT_ID?.trim();
  const clientSecret = process.env.GOOGLE_CLIENT_SECRET?.trim();

  if (Boolean(clientId) !== Boolean(clientSecret)) {
    throw new Error(
      "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must either both be set or both be omitted.",
    );
  }
  if (!clientId || !clientSecret) return undefined;
  return { clientId, clientSecret };
}

export function getClientIpAddressHeaders(): string[] {
  const configured = process.env.AUTH_TRUSTED_CLIENT_IP_HEADER
    ?.trim()
    .toLowerCase();
  if (!configured) return ["x-sodai-remote-address"];
  if (!["cf-connecting-ip", "x-forwarded-for"].includes(configured)) {
    throw new Error(
      "AUTH_TRUSTED_CLIENT_IP_HEADER must be cf-connecting-ip or x-forwarded-for.",
    );
  }
  return [configured, "x-sodai-remote-address"];
}

export function getServiceHost(): string {
  const host = process.env.AUTH_HOST?.trim() || "127.0.0.1";
  if (/[/\s]/.test(host)) {
    throw new Error("AUTH_HOST must be a hostname or IP address without whitespace or a path.");
  }
  return host;
}

export function getServicePort(): number {
  const configured = process.env.AUTH_PORT?.trim() || "3001";
  const port = Number(configured);
  if (!Number.isInteger(port) || port < 1 || port > 65_535) {
    throw new Error("AUTH_PORT must be an integer between 1 and 65535.");
  }
  return port;
}
