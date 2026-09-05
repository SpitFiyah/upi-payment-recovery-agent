# Decisions

ADR-style log of the choices that would come up in a panel round, plus the
ones the original spec did not cover and had to get decided mid-build.

## ADR 1: Streamlit only, no backend framework

FastAPI, Flask, and React were all explicitly ruled out. The demo audience is
a panel clicking through a UI, not an API consumer. Streamlit gives a single
Python file that is both the frontend and the backend, and Chandan already
knows the deploy path (Streamlit Community Cloud, one click from GitHub).
Adding a separate API layer would be surface area with no payoff at this
scope.

## ADR 2: JSONL over a database

200 records do not need PostgreSQL, MongoDB, or even SQLite. JSONL is
append-only, human-readable, greppable in front of a panel, and survives a
partial write if the process dies mid-batch. A database would add setup
friction for zero benefit at this scale.

## ADR 3: LLM is Tier 3/4, not Tier 1

The architecture puts a Python dict and a local embedding model ahead of any
LLM call. Measured result: 90% of the batch never touches an LLM at all.
This is the direct answer to the "AI Judgment" evaluation signal, since it
shows a real decision about where AI earns its cost and where it is
overkill, not "call the LLM for everything because it's the AI Buildathon."

## ADR 4: Python 3.13.14 instead of the spec's 3.12 target

The spec was written assuming Python 3.12, worried that 3.14 might break
sentence-transformers or Streamlit compatibility. The build machine has
3.13.14 and no 3.12 installed. Rather than lose 10-15 minutes installing a
second Python version on a night with a hard deadline, Chandan chose to
proceed on 3.13. Confirmed clean: `pip install -r requirements.txt` succeeded
with no version conflicts, and the full test suite (27 tests across every
tier and the recovery agent) passes on 3.13.14.

## ADR 5: Model swaps for both LLM providers

Both `gemini-2.0-flash` and Groq's `llama-3.3-70b-versatile`, the exact
models named in the original spec, had been retired by their providers by
the time this was built. Gemini's own 404 response named the direct
replacement (`gemini-3.6-flash`), so that one was a forced substitution, not
a judgment call. Groq's catalog no longer has any Llama 3.3 model at all, so
that one genuinely was a judgment call: asked Chandan directly rather than
guessing, and `openai/gpt-oss-120b` was picked as the closest capability
tier still on Groq's free plan. Full detail in `docs/FAILURE_LOG.md`,
Failures 1 and 2.

## ADR 6: Novel/ambiguous message templates added to the data generator

The original error message templates overlapped so heavily with both the
keyword tier's substrings and the embedding tier's 90 labeled examples that
a full 200-transaction batch produced literally zero LLM-tier
classifications. That would have made the entire "AI as last resort"
architecture untestable in the actual demo, since Tier 3/4 code would never
run outside of isolated unit tests. Added 12 templates (2 per RootCause
bucket) phrased distinctly enough to escalate past both deterministic
tiers, verified against `tier_keyword.classify()` and
`tier_embedding.classify()` individually before wiring them in, at a 10%
sampling weight. See `docs/FAILURE_LOG.md` for the details, and the Phase 5
commit message for the before/after tier split.

## ADR 7: should_stop() wired into the live retry loop, not just tested

Caught during Phase 6 while writing metrics: `retry_policy.should_stop()`
had unit tests but was never actually called from `recovery_agent.py`, which
just looped a plain `range()` over `max_attempts`. Since "stopping rules"
is one of the five things the Track 3 bar explicitly requires as a real
artifact, not just tested logic, this got fixed before moving on to
metrics. The attempts cap, 24h window, and $0.10 cost cap are all checked
on every simulated attempt now, though in practice only the attempts cap
realistically fires given the current policy numbers (max total elapsed
time across all policies tops out around 1.1 hours, nowhere near the 24h
window, and per-transaction classification cost tops out at $0.0001,
nowhere near the $0.10 cap).
