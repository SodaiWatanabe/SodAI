import "dotenv/config";

import { serve } from "@hono/node-server";
import { getConnInfo } from "@hono/node-server/conninfo";

import { createAuthServiceApp } from "./app.js";
import { auth } from "./auth.js";
import { authDatabasePool } from "./database.js";
import { getServiceHost, getServicePort } from "./environment.js";
import { authCapabilities } from "./options.js";

const hostname = getServiceHost();
const port = getServicePort();
const app = createAuthServiceApp({
  authHandler: auth.handler,
  capabilities: authCapabilities,
  readiness: async () => {
    await authDatabasePool.query("select 1");
  },
  remoteAddress: (context) => getConnInfo(context).remote.address,
});

const server = serve(
  {
    fetch: app.fetch,
    hostname,
    port,
  },
  ({ address, port: listeningPort }) => {
    console.info(`SodAI auth service listening on http://${address}:${listeningPort}`);
  },
);

let shuttingDown = false;

async function shutdown(signal: NodeJS.Signals): Promise<void> {
  if (shuttingDown) return;
  shuttingDown = true;
  console.info(`Received ${signal}; stopping the authentication service.`);

  const forceCloseTimer = setTimeout(() => {
    if (
      "closeAllConnections" in server &&
      typeof server.closeAllConnections === "function"
    ) {
      server.closeAllConnections();
    }
  }, 5_000);
  forceCloseTimer.unref();

  try {
    await new Promise<void>((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
    });
  } catch (error) {
    console.error("Failed to stop the authentication service cleanly.", error);
    process.exitCode = 1;
  } finally {
    clearTimeout(forceCloseTimer);
    await authDatabasePool.end().catch((error: unknown) => {
      console.error("Failed to close the authentication database pool.", error);
      process.exitCode = 1;
    });
  }
}

process.once("SIGINT", () => void shutdown("SIGINT"));
process.once("SIGTERM", () => void shutdown("SIGTERM"));
