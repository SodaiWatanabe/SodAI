import { Pool } from "pg";

import { requireServerEnvironment } from "./environment";

const globalForAuthDatabase = globalThis as typeof globalThis & {
  sodaiAuthDatabasePool?: Pool;
};

function createAuthDatabasePool(): Pool {
  return new Pool({
    application_name: "sodai-auth",
    connectionString: requireServerEnvironment("AUTH_DATABASE_URL"),
    connectionTimeoutMillis: 5_000,
    idleTimeoutMillis: 30_000,
    max: Number(process.env.AUTH_DATABASE_POOL_SIZE ?? 10),
    options: "-c search_path=auth,public",
  });
}

export const authDatabasePool =
  globalForAuthDatabase.sodaiAuthDatabasePool ?? createAuthDatabasePool();

if (process.env.NODE_ENV !== "production") {
  globalForAuthDatabase.sodaiAuthDatabasePool = authDatabasePool;
}
