# Architecture

## Pipeline

Every failed transaction moves through one linear path:

    preprocessing -> 4-tier classification cascade -> retry policy -> simulated retries -> audit log

`src/recovery_agent.py` is the orchestrator. It calls `src/classifier.py` for
classification, `src/retry_policy.py` for policy lookup and stopping rules, and
`src/audit_log.py` to write every step to `logs/audit.jsonl`. `asyncio.gather`
runs the batch concurrently, capped at 10 concurrent LLM calls via a semaphore
so a 200-transaction batch does not hammer the free-tier rate limits any
harder than necessary.

## Preprocessing

`src/preprocessing.py` runs on every transaction before classification even
starts. It pulls the bank code out of the UPI VPA suffix (`user@ybl` becomes
`YBL`) and looks for an embedded upstream error code (`E091`, `BLR-091`) in
the raw error message. This is plain regex, not a classification tier, and it
always runs.

## The 4-tier cascade (AI Judgment)

This is the core answer to the "AI Judgment" evaluation signal: the LLM is
the last resort, not the first tool.

1. **Tier 1, keyword match** (`src/tier_keyword.py`). A Python dict of
   substrings to RootCause. Zero cost, sub-millisecond.
2. **Tier 2, local embedding** (`src/tier_embedding.py`). sentence-transformers
   `all-MiniLM-L6-v2`, 90 labeled examples (15 per bucket), cosine similarity
   threshold of 0.75. Zero cost, 5-20ms.
3. **Tier 3, Gemini** (`src/llm_client.py`). Structured JSON output, parsed
   with pydantic v2, only reached when Tiers 1 and 2 both escalate.
4. **Tier 4, Groq fallback** (`src/llm_client.py`). Automatic switchover on
   any Gemini failure. If both fail, the transaction is classified UNKNOWN
   and routed to `notify_user`.

Measured on the current 200-transaction batch: keyword handled 76.5% of
traffic, embedding 13.5%, and the LLM tier the remaining 10% (of which 100%
landed on Groq this run, see `docs/FAILURE_LOG.md` Failure 4 for why). That
is not the 60/25/15 split originally targeted in the spec, it is what
actually happened, and the spec's own rule is to report the real number, not
the target.

## Retry policy and stopping rules (Compliant Escalation, Stopping Rules)

`src/retry_policy.py` holds a constants table, one `RetryPolicy` per
RootCause, each with a `max_attempts`, a list of `intervals_seconds`, a
`strategy`, and an `expected_recovery_rate`. `should_stop()` is checked on
every simulated attempt and enforces three independent caps:

- attempts cap, from the policy's `max_attempts`
- a 24 hour global time window
- a $0.10 global cost cap per transaction

For `notify_user`/`no_retry` policies with `max_attempts=0` (MANDATE_ERROR),
the system makes no retry attempt of its own, but still simulates one
self-resolution check, since `expected_recovery_rate` is defined for that
bucket too (the user might fix their own mandate after being notified).

## Audit trail

`src/audit_log.py` appends one JSON line per pipeline stage per transaction
to `logs/audit.jsonl`: `enriched`, `classified`, `policy_selected`, one
`retry_attempted` per simulated attempt, then a final `recovered` or
`abandoned`. Append-only, human-readable, survives partial writes, greppable
during a live demo. This is the audit trail the Track 3 bar calls for.

## Metrics (Measured, Batch)

`src/metrics.py` reads the audit log back and cross-references it against the
synthetic data's ground-truth `true_root_cause` (stashed in each
transaction's metadata at generation time) to compute a real confusion
matrix and macro F1, not self-reported accuracy. It also reports per-bucket
recovery rate, tier routing distribution, cost per recovery, the Groq
fallback rate, and which stopping rule ended each abandoned transaction.

## UI

`app.py` is the entire frontend, a single Streamlit file with four tabs:
Metrics, Transactions Table, Drilldown, and Random Failures. The last one
exists specifically to counter cherry-picking: it samples 5 abandoned
transactions at random and shows their full audit trail, not hand-picked
success stories.
