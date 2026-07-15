import "dotenv/config";

import { getMigrations } from "better-auth/db/migration";

import { authDatabasePool } from "../src/database.js";
import { authOptions } from "../src/options.js";

const checkOnly = process.argv.includes("--check");

async function main(): Promise<void> {
  const schemaResult = await authDatabasePool.query<{
    current_schema: string | null;
  }>("select current_schema() as current_schema");

  if (schemaResult.rows[0]?.current_schema !== "auth") {
    throw new Error(
      `Refusing to migrate outside the auth schema (current: ${schemaResult.rows[0]?.current_schema ?? "none"}).`,
    );
  }

  const migrations = await getMigrations(authOptions);
  const pendingTables = migrations.toBeCreated.length;
  const pendingColumns = migrations.toBeAdded.reduce(
    (count, migration) => count + Object.keys(migration.fields).length,
    0,
  );

  if (pendingTables === 0 && pendingColumns === 0) {
    console.info("Better Auth schema is up to date.");
    return;
  }
  if (checkOnly) {
    console.error(
      `Better Auth schema has pending changes: ${pendingTables} table(s), ${pendingColumns} column(s).`,
    );
    process.exitCode = 1;
    return;
  }

  await migrations.runMigrations();
  console.info(
    `Applied Better Auth schema changes: ${pendingTables} table(s), ${pendingColumns} column(s).`,
  );
}

try {
  await main();
} finally {
  await authDatabasePool.end();
}
