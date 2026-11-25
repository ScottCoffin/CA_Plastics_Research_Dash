import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";
import { cloudflareTest, readD1Migrations } from "@cloudflare/vitest-pool-workers";

// Tests run inside workerd with a local D1 (miniflare). Test-only bindings override the
// production defaults: outbox mail instead of Resend, and fake secrets.
export default defineConfig(async () => {
  const migrations = await readD1Migrations(fileURLToPath(new URL("./migrations", import.meta.url)));
  return {
    plugins: [
      cloudflareTest({
        wrangler: { configPath: "./wrangler.toml" },
        miniflare: {
          bindings: {
            TEST_MIGRATIONS: migrations,
            MAIL_MODE: "outbox",
            TURNSTILE_SECRET: "test-turnstile-secret",
            SESSION_SIGNING_KEY: "test-session-signing-key-0123456789abcdef",
            EMAIL_HASH_KEY: "test-email-hash-key-0123456789abcdef",
            ORCID_CLIENT_ID: "APP-TEST-0000000000",
            ORCID_CLIENT_SECRET: "test-orcid-client-secret",
          },
        },
      }),
    ],
    test: {
      include: ["test/**/*.test.ts"],
      setupFiles: ["./test/setup.ts"],
    },
  };
});
