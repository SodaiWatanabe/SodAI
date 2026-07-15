const HOP_BY_HOP_REQUEST_HEADERS = [
  "connection",
  "content-length",
  "host",
  "transfer-encoding",
  "upgrade",
  "x-sodai-remote-address",
];
const AUTH_PROXY_TIMEOUT_MS = 30_000;

type AuthProxyDependencies = {
  fetch?: typeof fetch;
  serviceUrl: string;
};

export async function proxyAuthRequest(
  request: Request,
  dependencies: AuthProxyDependencies,
): Promise<Response> {
  const incomingUrl = new URL(request.url);
  const targetUrl = new URL(
    `${incomingUrl.pathname}${incomingUrl.search}`,
    dependencies.serviceUrl,
  );
  const headers = new Headers(request.headers);
  for (const name of HOP_BY_HOP_REQUEST_HEADERS) headers.delete(name);

  const init: RequestInit & { duplex?: "half" } = {
    cache: "no-store",
    headers,
    method: request.method,
    redirect: "manual",
    signal: AbortSignal.any([
      request.signal,
      AbortSignal.timeout(AUTH_PROXY_TIMEOUT_MS),
    ]),
  };
  if (request.body) {
    init.body = request.body;
    init.duplex = "half";
  }

  try {
    return await (dependencies.fetch ?? fetch)(targetUrl, init);
  } catch {
    return Response.json(
      { code: "AUTH_SERVICE_UNAVAILABLE" },
      {
        headers: { "Cache-Control": "no-store" },
        status: 502,
      },
    );
  }
}
