# afnan's timeline

A terminal-style log of the actual build session for this repo, 2026-09-05.
Timestamps are pulled straight from `git log`, not reconstructed from memory.
Narration between commits explains what happened and why, including the
parts that broke.

```
$ git log --reverse --pretty=format:"%h  %ad  %s" --date=format:"%Y-%m-%d %H:%M:%S"

18:30:49  4100b5b  Scaffold repo: structure, deps, AGENTS.md spec, pydantic models
```

Environment check first: Python 3.13.14 on this machine, no 3.12 available.
Spec wanted 3.12. Decision: proceed on 3.13 rather than lose 10-15 minutes
installing a second Python. `pip install -r requirements.txt` ran clean,
zero conflicts, so that call held up.

Scaffolded the full repo layout, wrote AGENTS.md as the source-of-truth spec
(symlinked CLAUDE.md to it), set up `.gitignore`/`.env`, `git init`, created
the public GitHub repo via `gh repo create`, first commit pushed.

```
18:32:40  f043317  Add synthetic transaction generator (Phase 2)
```

`src/data_generator.py` writing 200 synthetic UPI failures, biased toward
BANK_TIMEOUT and NETWORK_ERROR per NPCI's public failure-rate reporting.
Schema + distribution tests passed on the first run.

```
18:39:59  16dab18  Add async LLM client with Gemini primary, Groq fallback (Phase 3)
```

This is where the night got interesting. Wrote the async LLM client, ran a
live smoke test, and immediately hit two dead models:

- Groq's `llama-3.3-70b-versatile` (the spec's exact pick) is gone, 404,
  retired. Asked instead of guessing, landed on `openai/gpt-oss-120b`.
- Gemini's `gemini-2.0-flash` is also gone. Google's own 404 message named
  the replacement directly (`gemini-3.6-flash`), so that one didn't need a
  judgment call.
- On top of that, `GenerateContentConfig(timeout=...)` isn't a real field,
  pydantic rejected it with `extra_forbidden`. Timeout actually lives under
  a nested `http_options` object. Every Gemini call was dying silently
  before this got caught, all traffic quietly falling to Groq.

All three logged in `docs/FAILURE_LOG.md` before being fixed, per the rule
that failures get written down before the fix goes in, not after.

```
18:44:49  d1eca70  Add local embedding tier with 90 labeled examples (Phase 3.5)
```

sentence-transformers `all-MiniLM-L6-v2`, 90 labeled examples (15 per
RootCause bucket), cosine threshold 0.75. Approval-gate check
(`classify('insufficient balance in account')`) returned the right bucket
on the first try.

```
18:49:59  ca1df45  Add full cascade orchestrator, preprocessing, retry policy (Phase 4)
```

Wired preprocessing (regex bank-code + error-code extraction), the keyword
tier, the retry policy constants table, and the orchestrator that chains
all four tiers together. Ran a real single-transaction test through all
three escalation paths (keyword hit, embedding hit, LLM escalation on a
genuinely novel message) to confirm the cascade actually works end to end,
not just in isolated unit tests.

```
20:29:09  f172408  Add recovery agent orchestrator and audit log (Phase 5)
```

Roughly 1h40m gap here, most of it spent on something that doesn't show up
in the diff: running the full batch and noticing zero transactions ever
reached the LLM tier. The original error message templates overlapped so
heavily with the keyword substrings and the embedding tier's own labeled
examples that Tier 3/4 code was structurally unreachable in a real batch,
only ever exercised by hand-written test cases. Added 12 novel/ambiguous
templates (2 per bucket), verified each one individually against both
deterministic tiers before wiring them in at 10% sampling weight. That's
the fix that actually shipped in this commit, alongside `audit_log.py` and
`recovery_agent.py` themselves. Full batch of 200: ~20 seconds.

```
21:08:15  52d577f  Wire retry_policy.should_stop into the live retry loop (Phase 5 fix)
```

Caught while writing the metrics code: `should_stop()` had unit tests but
was never actually called from the live retry loop, which just used a plain
`range()`. Since "stopping rules" is one of the four things the Track 3 bar
explicitly requires as a real, running artifact, this got fixed before
metrics got written on top of it.

```
21:11:45  b9f302c  Add metrics computation (Phase 6)
21:17:47  8c57ce9  Document Gemini's 0% hit rate in full batch runs (FAILURE_LOG 4)
```

Metrics came back sane: 71.0% overall recovery, macro-F1 0.959, confusion
matrix concentrated exactly where you'd expect (a handful of genuinely
ambiguous UNKNOWN messages getting misread as LIMIT_EXCEEDED). One number
looked wrong at first: 100% of LLM-tier calls landed on Groq, not Gemini,
despite Gemini working fine in isolated single-call tests. Tried dropping
concurrency from 10 to 3 to rule out a rate-limit burst, barely moved the
needle. Logged it honestly as a probable quota ceiling from the night's
testing volume rather than pretending it away.

```
21:55:34  d971a3c  Add Streamlit UI: Metrics, Transactions, Drilldown, Random Failures (Phase 7)
```

Single-file `app.py`, four tabs. No browser tools available this session,
so verified it with Streamlit's own `AppTest` framework instead of eyeballing
it in a browser: all four tabs render with zero exceptions, the 200-option
drilldown selectbox works, the Random Failures button samples without
error.

```
21:59:44  e496253  Add architecture, decisions, roadmap docs and fill README (Phase 9)
```

Filled in the real measured numbers, wrote ARCHITECTURE.md tying each piece
back to the four evaluation signals, DECISIONS.md as an ADR log covering
every judgment call above, ROADMAP.md as the six-month vision.

## Still open

- **Streamlit Cloud deploy** (Phase 8): needs a browser-based GitHub OAuth
  step, no browser tools this session, has to be done by hand at
  share.streamlit.io.
- **Pitch video** (Phase 10) and **form submission** (Phase 11): both need
  the live demo URL from the step above, plus an actual human recording.
- Repo access: c0mbateRxd added as a collaborator. Attempted to raise them
  to admin so they could invite others, the API keeps returning success
  (204) but the permission stays at "write" on every check, confirmed with
  a raw curl call too. Looks like a restriction on the token `gh` is using,
  not a mistake in the request. Needs doing by hand in the repo's Settings
  to Collaborators page.
