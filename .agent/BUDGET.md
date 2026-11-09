# Delegation Budget

The owner authorized the work on 2026-11-07 under the Codex Pro subscription,
not API billing. Token-dollar usage is therefore unavailable and is not a
meaningful control for this run.

| Limit | Owner-set cap | Current tracked usage |
|---|---:|---:|
| Fresh worker sessions | `18` | `14` |
| Incremental paid API/model spend | `$0` | `$0` |
| External service/network spend | `$0` | `$0` |

The 18-session cap permits one initial Luna session and at most one fresh Luna
correction for each of L1-L9. Stop before session 19, on any request for paid
API usage, or when the Pro plan prevents further model use. Record each session
in `.agent/DELEGATION_LOG.md`; record token usage only if the product exposes it.
