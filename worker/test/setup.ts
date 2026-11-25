import { applyD1Migrations, env } from "cloudflare:test";

// Runs before each test file: a fresh local D1 with the migrations from migrations/.
await applyD1Migrations(env.DB, env.TEST_MIGRATIONS);
