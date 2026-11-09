# SPK-7 verification guide

The benchmark is intentionally offline by default:

```powershell
py -3.14 scripts/benchmark_openalex_costs.py
```

This prints the exact 100-call plan without touching the network. The unit
tests exercise plan size, dry-run behavior, opt-in gates, metric capture,
credential redaction, bounds, and cost-limit aborts using a mock transport.

Owner authorization dated 2026-11-09 is recorded in
`docs/api_notes/openalex_free_only_owner_confirmation_2026-11-09.md`: the
account is free-only, has no prepaid balance or paid plan, and has no paid
fallback or billing changes authorized. Live invocation uses that artifact,
the operator's explicit acknowledgement, and a USD 0.25 hard cost limit:
`py -3.14 scripts/benchmark_openalex_costs.py --live
--ack-zero-paid-credit-policy --preflight-proof docs/api_notes/openalex_free_only_owner_confirmation_2026-11-09.md
--max-cost-usd 0.25`. The proof contents are not read or logged; the script
cannot independently verify account state.

The completed 2026-11-09 run used the documented `/rate-limit` status endpoint
after the 100 calls; the result and its USD 0.002 reconciliation difference
are recorded separately in
`docs/api_notes/openalex_rate_limit_2026-11-09.json` and
`docs/api_notes/openalex_costs.md`. The historical CLI output has aggregates
only; the original usage log has no per-call latency, so no latency was
reconstructed. Future benchmark responses persist sanitized per-call latency
records. The script uses no retries
and records the failing endpoint, call index, category and latency for partial
runs. A transport failure has no cost field; HTTP response costs are recorded
only when actually returned. Future live runs still need fresh owner approval
and the explicit per-run ceiling.

S2.1 reads `config/budget.yml`, environment overrides, and caller-supplied
limits and applies the strictest USD and credit caps. It uses the higher of
response USD metadata and the measured credit conversion, reserves the
planned-request bound before a request, and counts same-day OpenAlex records in
its local usage log across reruns. This is a conservative local guard, not a
provider account-balance guarantee; the currently in-flight request can exceed
its reserve before a response exposes its actual charge.
