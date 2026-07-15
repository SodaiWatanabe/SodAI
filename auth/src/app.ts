import { Hono, type Context } from "hono";

export type AuthServiceCapabilities = Readonly<{
  google: boolean;
}>;

type AuthRequestHandler = (request: Request) => Response | Promise<Response>;
type RemoteAddressResolver = (context: Context) => string | undefined;
type ReadinessCheck = () => Promise<void>;

export function createAuthServiceApp(options: {
  authHandler: AuthRequestHandler;
  capabilities: AuthServiceCapabilities;
  readiness?: ReadinessCheck;
  remoteAddress?: RemoteAddressResolver;
}) {
  const app = new Hono();

  app.get("/healthz", (context) => context.json({ status: "ok" }));
  app.get("/readyz", async (context) => {
    try {
      await options.readiness?.();
      return context.json({ status: "ready" });
    } catch {
      return context.json({ status: "unavailable" }, 503);
    }
  });
  app.get("/api/auth/capabilities", (context) => {
    context.header("Cache-Control", "no-store");
    return context.json(options.capabilities);
  });
  app.on(["GET", "POST"], "/api/auth/*", (context) => {
    const remoteAddress = options.remoteAddress?.(context);
    if (!remoteAddress) return options.authHandler(context.req.raw);

    const headers = new Headers(context.req.raw.headers);
    headers.set("x-sodai-remote-address", remoteAddress);
    return options.authHandler(new Request(context.req.raw, { headers }));
  });

  return app;
}
