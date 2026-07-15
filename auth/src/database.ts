import { Pool } from "pg";

import { requireEnvironment } from "./environment.js";

function getPoolSize(): number {
  const configured = process.env.AUTH_DATABASE_POOL_SIZE?.trim() || "10";
  const size = Number(configured);
  if (!Number.isInteger(size) || size < 1 || size > 100) {
    throw new Error("AUTH_DATABASE_POOL_SIZE must be an integer between 1 and 100.");
  }
  return size;
}

export const authDatabasePool = new Pool({
  application_name: "sodai-auth",
  connectionString: requireEnvironment("AUTH_DATABASE_URL"),
  connectionTimeoutMillis: 5_000,
  idleTimeoutMillis: 30_000,
  max: getPoolSize(),
  options: "-c search_path=auth,public",
});
