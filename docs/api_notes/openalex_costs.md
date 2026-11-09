# OpenAlex cost measurement

**Status: 100-call SPK-7 measurement complete (2026-11-09).** The separate
owner-only artifact `openalex_free_only_owner_confirmation_2026-11-09.md`
records free-only/no-paid authorization. The provider's separate sanitized
`openalex_rate_limit_2026-11-09.json` records the worker's authenticated
`/rate-limit` response after the run. The run used ID
`openalex-bench-5c9fe4e0487b`, made 100/100 calls, and stopped without errors.

The original ignored log contains 100 request entries and one summary entry,
but no per-call latency values. The durable
`openalex_costs_run_2026-11-09.json` preserves the historical aggregate values
from the completed CLI output and marks the unavailable per-call values. No
per-call latency has been reconstructed. Future runs add one sanitized
`benchmark_call` JSONL record per response (endpoint, call index, status,
latency, credits, response metadata cost, conservative accounted cost); the
log remains ignored local output and can be summarized into a versioned artifact
after a future measurement.

Run `py -3.14 scripts/benchmark_openalex_costs.py` to print the offline plan.
It makes no network calls by default. Live mode makes 20 sequential requests for
each of five request shapes (100 planned calls): filter-only list,
search-filter count, grouped works, one singleton work, and a 200-row works
page. Each response's credit header and `meta.cost_usd` are recorded with
latency summaries; URL credentials are redacted through the shared cost logger.

Live mode requires the owner-confirmation artifact as `--preflight-proof`, a
USD 0.25 run ceiling, an environment-provided `OPENALEX_API_KEY` (or the
existing `.env` key alias), and the explicit zero-paid-credit acknowledgement.
The script checks only that the proof file exists; it cannot independently
establish current provider balance or guarantee that a request will be free.
Requests are sequential, have a bounded timeout, and are not retried. A
provider budget/rate-limit response stops the run and is recorded without
inventing cost for a request that received no response.

## Observed benchmark

All entries below are means over 20 sequential requests per shape. Costs are
the sum of each successful response's `meta.cost_usd`; credits are summed from
`X-RateLimit-Credits-Used`.

| Request shape | Calls | Credits | Observed cost (USD) | Mean latency (ms) | Max latency (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Filter-only list | 20 | 20 | 0.002 | 506.227 | 948.593 |
| Search-filter count | 20 | 200 | 0.020 | 409.749 | 723.566 |
| Group by publication year | 20 | 20 | 0.002 | 254.087 | 457.475 |
| Singleton work | 20 | 20 | 0.000 | 381.525 | 554.044 |
| 200-row page | 20 | 20 | 0.002 | 2047.787 | 3982.391 |
| **Total / weighted** | **100** | **280** | **0.026** | **719.875** | **3982.391** |

After the benchmark, the documented authenticated `/rate-limit` endpoint
returned a USD 1.00 daily limit, USD 0.972 remaining, 10,000-credit limit,
9,720 credits remaining, and zero prepaid or one-time balance. Its total 280
credits used matched the benchmark response headers. The allowance decrement
implies USD 0.028 used, USD 0.002 above the sum of response `meta.cost_usd`.
Preserve this discrepancy; do not treat response cost metadata and balance
decrement as interchangeable until reconciled. The status response was captured
after the benchmark, so no pre-run daily balance was recorded.

`config/budget.yml` sets the daily ceiling observed in the provider status
response and a USD 0.25 abort threshold. S2.1 resolves the strictest applicable
limit from config, `OPENALEX_MAX_COST_USD` / `OPENALEX_MAX_CREDITS`, and caller
limits. It uses `max(response meta.cost_usd, credits * cost_per_credit_usd)`
per request, reserves the measured maximum planned-request bound before each
request, and sums this UTC day's OpenAlex request records in the configured
usage log so reruns share a local daily guard. The historical records used only
metadata cost; replaying them under the measured USD 0.0001/credit conversion
raises the conservative total to USD 0.028 and counts the zero-metadata-cost
singleton credits.

The guard is not an exact account-balance monitor: it cannot see external calls
missing from the local usage log, and a live request can cost more than its
planned reserve before the response exposes that cost. If so, the post-response
check stops the run before snapshot/output/high-water advancement, but it
cannot undo provider usage already incurred. Check the provider `/rate-limit`
status before an ingestion run when other tools may have used the account.

The old add-on specification assumptions (100,000 daily credits, zero-cost
singleton, and USD 0.00001 per credit) are superseded for implementation by the
2026-11-09 observed/provider values: 10,000-credit daily limit, one singleton
credit per response despite USD 0.000 metadata cost, and USD 0.0001 per credit
from the daily budget and credit limit. No `docs/add_on_spec.md` or `.agent`
file was altered.

OpenAlex documents a free $1/day budget and the authenticated status endpoint
in its [pricing overview](https://help.openalex.org/access/pricing/) and
[authentication and rate-limit guidance](https://help.openalex.org/api/authentication/).
The USD 0.002 mismatch between response metadata sum and provider budget
decrement is accounted for conservatively by charging each response at the
higher of the two measured cost bases. Do not claim the post-run status is a
pre-run balance.

The AT-1 status call is an account-usage observation, not a metered request.
Its sanitized record preserves daily budget/usage/remaining values, credit
limits/usage/remaining values, prepaid and one-time balances, and reset time,
with `request_cost_known: false`; no zero request cost is invented. The local
metered-request subtotal excludes only the exact `/rate-limit` endpoint. This
classification preserves historical unknown status rows as diagnostics while
ordinary unknown-cost request rows continue to fail closed. AT-1 requires a
fresh valid provider snapshot before any sampling request and stops on malformed
status data or nonzero paid balances.

OpenAlex documents the `/rate-limit` response with `resets_at` and
`resets_in_seconds` (see its [rate limit and authentication guide](https://help.openalex.org/api/authentication/)).
The AT-1 adapter accepts that wire field; the older sanitized artifact's
`resets_in_seconds_at_capture` label is treated as an annotation, not a required
provider field. When no countdown is returned, the audit derives it from the
UTC observation clock and `resets_at`, while retaining the freshness bound.
