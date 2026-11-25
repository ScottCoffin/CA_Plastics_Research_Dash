import type { D1Migration } from "@cloudflare/vitest-pool-workers";
import type { Env } from "../src/env";

// Types the `env` exported by cloudflare:test (it reads the global Cloudflare.Env).
declare global {
  namespace Cloudflare {
    interface Env extends Omit<import("../src/env").Env, "DB"> {
      DB: D1Database;
      TEST_MIGRATIONS: D1Migration[];
    }
  }
}

export type { Env };
