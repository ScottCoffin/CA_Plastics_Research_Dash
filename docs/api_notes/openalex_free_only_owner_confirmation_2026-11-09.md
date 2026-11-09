# OpenAlex free-only authorization

**Date:** 2026-11-09

The owner confirmed that the OpenAlex account is free-only, has no prepaid
balance and has no paid plan. The authorized policy is to use the daily free
allowance only, with no paid fallback and no billing changes. This records the
owner's attestation; it is not an independent provider-side account check.

This confirmation permits a bounded benchmark only within the daily free
allowance. Use a per-run stop of USD 0.25, run requests sequentially with no
retries, and stop on provider budget/rate-limit errors. Do not store API keys,
account identifiers, or other account-specific information in this artifact.
