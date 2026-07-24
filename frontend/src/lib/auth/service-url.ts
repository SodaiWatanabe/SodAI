const DEFAULT_AUTH_SERVICE_URL = "http://127.0.0.1:13201";

export function getAuthServiceUrl(): string {
  const configured = process.env.AUTH_SERVICE_URL?.trim() || DEFAULT_AUTH_SERVICE_URL;
  let url: URL;

  try {
    url = new URL(configured);
  } catch {
    throw new Error("AUTH_SERVICE_URL must be a valid absolute URL.");
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("AUTH_SERVICE_URL must use http or https.");
  }
  if (url.pathname !== "/" || url.search || url.hash) {
    throw new Error("AUTH_SERVICE_URL must be an origin without a path, query, or hash.");
  }
  return url.origin;
}
