/** The only outbound fetch used by sign-up lookups. Injected through handle() so tests can replace it. */
export type Fetch = (input: string, init?: RequestInit) => Promise<Response>;

/** Resolves globalThis.fetch at call time, so a test that replaces it intercepts these calls too. */
export const liveFetch: Fetch = (input, init) => fetch(input, init);
