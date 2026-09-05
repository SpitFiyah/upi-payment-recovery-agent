# AGENTS.md

Cross-tool operating context for coding agents on this repo. Read completely before
writing any code, creating any files, or making any design decisions. If unclear, ask
directly. Do not fill gaps with assumptions.

Compatible with: Claude Code (via symlink from CLAUDE.md), Codex, Cursor, Copilot,
Aider, Windsurf, Antigravity CLI, and any other agent that reads the AGENTS.md spec.

**Approved deviations from the original spec (locked in at Phase 0, 2026-09-05):**
- Build environment is Windows, not Omarchy/Arch Linux. Use `.venv\Scripts\activate`,
  not `source .venv/bin/activate`.
- Python 3.13.14 is what's installed, not 3.12. No 3.12 available on this machine.
  Chandan chose to proceed on 3.13 rather than lose time installing 3.12. If
  sentence-transformers or Streamlit break on 3.13, fall back to installing 3.12.
- GitHub repo name: `upi-payment-recovery-agent`. Local folder: `D:\razorpay-mvp`.

---

## 0. GOVERNING PRINCIPLES (Karpathy's Four)

These override everything else in this file. When any other rule conflicts with these,
these win.

### 0.1 Think before coding
State assumptions before you write code. Surface tradeoffs when a choice has
meaningful alternatives. Ask when unclear rather than guessing. A wrong assumption
compounds through every file you write after it.

### 0.2 Simplicity first
No speculative features. No abstractions used exactly once. Minimum code that
satisfies the current request. If you feel the urge to add a config flag "in case we need it
later," delete the urge. Add it when we need it.

### 0.3 Surgical changes
Do not touch adjacent code, comments, imports, formatting, or naming when the user
did not ask for that. Match the existing style of the file you are editing, even if you
disagree with it. Every changed line should trace directly to the request. If you notice
something worth fixing that is out of scope, note it in FAILURE_LOG.md or say it in chat,
do not fix it silently.

### 0.4 Verify against explicit goals
Every phase in this spec has a "runnable state" and an "approval gate." Do not claim a
phase complete until both are actually satisfied. Do not claim a test passes without
running it. Do not claim a metric without measuring it.

These are working when: fewer unnecessary changes in diffs, fewer rewrites due to
overbuilding, tests that meaningfully verify what was requested.

---

## 1. WHO YOU ARE HELPING AND WHY

User: Chandan, applying to the Razorpay AI Buildathon 2026 (Track 3: AI Revenue
Recovery).

Goal: Submit a working, measured, honest project that clears the shortlist bar. Not
perfection. Working + measured + honest.

Time reality: Deadline is Sept 5, 11:59 PM IST. Realistic build window is 13-15 hours
after sleep. All-4-tier full-send plan. Cutting corners on scope is worse than cutting
corners on polish. If forced to choose, ship a working thing without a video versus a
broken thing with a video.

---

## 2. USER PROFILE AND HARD PREFERENCES

Enforce these across every message, every file, every doc string.

### Communication style
- Blunt, direct assessments. No hedging, no fluff, no cheerleading.
- Structured outputs (tables, bullets, numbered lists) when they help clarity.
- Terse in chat replies. Detailed in code comments and docs.
- Approves plans before execution. For multi-file operations or design decisions not
  covered here, propose 2-3 options and wait for approval.
- Complete runnable files. Never send diffs, partial snippets, or "insert this here"
  instructions when a full file is warranted.

### Written output rules
- **No em-dashes anywhere.** Use commas, colons, periods, or restructure the
  sentence. Applies to code comments, docs, README, form answers, video script,
  commit messages, UI text, terminal output. Everything.
- **Human-sounding written content.** README, DECISIONS.md, FAILURE_LOG.md,
  form field answers, video script must not read like AI wrote them. Vary sentence
  length. Include specific numbers. Avoid these AI stock phrases: leveraging,
  cutting-edge, seamless, robust solution, state-of-the-art, at scale, empowering,
  unlock, harness.
- Casual terse tone in Chandan-facing chat is normal.

### Skill level (self-reported, treat as ground truth)
- **Python:** comfortable with basics (variables, functions, loops, imports, standard
  library).
- **LLM API calls:** done before.
- **Deployment:** yes (Vercel, Render, Railway, Streamlit Cloud).
- **FastAPI, Flask, Express:** NO. Do not introduce a backend web framework.
  Streamlit is the entire "frontend + backend."
- **React or other JS frameworks:** no.
- **C++:** learning separately for DSA, not for this project.
- **Docker/containers:** no.

### Environment
- Windows 11. Python 3.13.14. GitHub CLI authenticated as SpitFiyah.
- Has: Gemini API key, Groq API key (both freshly rotated).
- GitHub account, will create public repo `upi-payment-recovery-agent`.

---

## 3. RAZORPAY BUILDATHON EVALUATION CRITERIA

Every architecture decision must serve at least one of these signals. Reference them by
name in code comments and docs where relevant.

1. **Problem Taste** — meaningful, real-world financial/merchant problem. Not a toy
   demo.
2. **Build Quality** — clean repo, runs on any machine, clear setup. Panel must be able
   to clone and run in under 15 minutes.
3. **AI Judgment** — LLM only where it adds genuine value. Deterministic rules where
   AI would be overkill or unauditable.
4. **Failure Recovery** — documented failures during development, honest limitations
   list. FAILURE_LOG.md is graded.

Track 3 stated bar (verbatim from Razorpay): "Show measured money recovered
across a batch, with compliant escalation, stopping rules, and an audit trail."

Every one of "measured", "batch", "compliant escalation", "stopping rules", "audit trail"
must show up as a real artifact in the repo.

---

## 4. PROJECT IDENTITY

- **Name:** UPI Payment Failure Recovery Agent
- **Track:** Track 3 (AI Revenue Recovery)
- **One-line tagline:** Detects UPI payment failures, classifies root cause via a
  multi-tier cascade with LLM as last resort, executes a bounded retry strategy with
  deterministic stopping rules, and reports measured recovery across a batch with
  full audit trail.
- **Submission targets:**
  1. Public GitHub repo (must clone and run in under 15 min)
  2. Live Streamlit Cloud demo URL
  3. 5-minute pitch video (YouTube unlisted)
  4. Google Form submission at forms.gle/d9r2gvxp8cmoZhon9

---

## 5. PROBLEM STATEMENT

Indian merchants using UPI experience payment failure rates in the 4-6% range publicly
reported by NPCI. Each failed transaction is potentially recoverable revenue if:

- Root cause is correctly identified from the raw upstream error message
- The right retry strategy is chosen (immediate vs delayed vs alternate rail vs notify
  user)
- Retry cadence respects merchant tolerance and user friction thresholds
- The system knows when to stop pushing (max attempts, cost cap, time window,
  compliance)

Current state in production: most merchants either do naive fixed-interval retries or
nothing. Both leak money.

This agent closes the loop: enrich, classify, decide policy, execute, verify, log.

---

## 6. ARCHITECTURE: MULTI-TIER CASCADE

Core strategy: AI is the last resort, not the first tool. Every incoming failed transaction
runs through preprocessing, then a 4-tier classification cascade.

### Preprocessing (always runs, not a classification tier)
- Regex extracts bank code from UPI VPA suffix. `user@ybl` gives YBL, `user@paytm`
  gives PAYTM, `user@okhdfcbank` gives HDFC.
- Regex extracts embedded bank error codes if present (e.g., "E091", "BLR-091").
- Enriches every transaction with structured metadata before classification begins.

### Tier 1: Keyword pattern match
- Python dictionary mapping known substrings to RootCause.
- Examples: "insufficient" maps to INSUFFICIENT_BALANCE, "timeout" or
  "unreachable" map to BANK_TIMEOUT, "limit exceeded" maps to LIMIT_EXCEEDED,
  "mandate" maps to MANDATE_ERROR.
- Cost $0, latency under 1ms.
- Targeted at roughly 60% of traffic. Measure actual after Phase 6.

### Tier 2: Local embedding plus kNN
- sentence-transformers with `all-MiniLM-L6-v2` (80MB, runs on CPU, no GPU).
- 15 labeled example error messages per RootCause bucket (90 total labeled
  examples).
- Cosine similarity threshold strictly greater than 0.75.
- If highest similarity below threshold, escalate to Tier 3.
- Cost $0, latency 5-20ms.
- Targeted at additional 25% of traffic.

### Tier 3: Gemini 2.0 Flash
- Structured JSON mode with RootCause enum values injected into the prompt.
- pydantic v2 parsing on the response, defaulting to UNKNOWN on schema violation.
- Only novel/ambiguous messages reach this tier.
- Cost ~$0.0001 per call, latency ~1s.
- Targeted at remaining 15% of traffic.

### Tier 4: Groq fallback (Llama 3.3 70B)
- Automatic switchover on Gemini timeout, rate limit, or 5xx error.
- Same JSON contract as Tier 3.
- If both APIs fail: classify as UNKNOWN, route to notify_user policy. No further
  fallback.

### AI vs deterministic split (for panel defense)

**LLM handles:**
- Classifying novel error messages that keyword and embedding tiers could not
  confidently handle.

**Deterministic handles everything else:**
- Preprocessing (regex extraction)
- Tier 1 keyword classification
- Tier 2 embedding + kNN (technically a local model, but not "AI" in the LLM sense)
- Retry policy selection (constants table)
- Stopping rules (boolean logic)
- Retry timing (predetermined intervals)
- Success/failure simulation (probability tables from NPCI data)
- Metrics computation (pandas/pure Python)
- Cost tracking

---

## 7. TECH STACK DECISIONS

Each choice must be defensible in the panel round. Rationale column doubles as
material for docs/DECISIONS.md.

| Component | Choice | Rationale |
|---|---|---|
| Language | Python 3.13 (3.12 spec target, 3.13 approved deviation) | LLM SDKs Python-first. HTTP orchestration natural. Panel reads Python fastest. Runtime speed irrelevant because LLM API latency dominates. |
| Concurrency | asyncio + asyncio.gather | Parallel LLM calls. Batch of 200 targeted under 2 minutes end-to-end. |
| UI | Streamlit | Single Python file. No separate frontend framework. Demo IS the UI. |
| LLM primary | Google Gemini 2.0 Flash | Free tier covers 200-txn batch with margin. Fast. JSON mode. |
| LLM fallback | Groq (Llama 3.3 70B) | Free tier, fastest inference available. Automatic switchover. Shows reliability engineering. |
| Local classifier | sentence-transformers all-MiniLM-L6-v2 | 80MB, CPU-only, 5-20ms latency, $0 cost. Handles semantic matches where keywords fail. |
| Storage | JSONL (audit log = append-only) | Zero setup. Portable. Human-readable. Grepable for panel demo. 200 records don't need a database. |
| Deployment | Streamlit Community Cloud | Free. One-click from GitHub. Public URL. Handles env secrets. |
| Testing | pytest | Standard. Focused on classifier and retry policy in isolation. |
| Env vars | python-dotenv | Standard pattern. Never commit .env. |
| Schema | pydantic v2 | Catches LLM output drift at parse time. |

### Explicitly NOT using and why
- **FastAPI/Flask:** Streamlit is enough. No backend layer needed for this demo.
- **React/Vue:** Streamlit handles UI.
- **PostgreSQL/MongoDB/SQLite:** JSONL is enough for 200 records.
- **Docker:** Streamlit Cloud handles deploy.
- **LangChain/LangGraph:** adds abstraction the panel would question at this scope.
- **Ollama or local LLMs (as fallback beyond Groq):** unnecessary complexity. If both
  cloud APIs die, UNKNOWN bucket handles it.
- **TEE:** not needed for synthetic data. Talking point for Q6, not build target.

---

## 8. DATA MODEL

All schemas in `src/models.py` using pydantic v2.

### Transaction
```python
class Transaction(BaseModel):
    txn_id: str            # uuid4
    merchant_id: str        # e.g. "MERCH_042"
    amount_inr: float       # 100.00 to 50000.00
    upi_vpa: str             # e.g. "user@ybl", "user@paytm"
    timestamp: datetime
    status: Literal["failed"]
    raw_error_message: str   # free text from upstream
    bank_code: str           # populated by preprocessing regex
    metadata: dict           # optional
```

### RootCause enum (6 buckets)
```python
class RootCause(str, Enum):
    BANK_TIMEOUT = "bank_timeout"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    MANDATE_ERROR = "mandate_error"
    NETWORK_ERROR = "network_error"
    LIMIT_EXCEEDED = "limit_exceeded"
    UNKNOWN = "unknown"
```

### RetryPolicy
```python
class RetryPolicy(BaseModel):
    cause: RootCause
    max_attempts: int
    intervals_seconds: list[int]
    strategy: Literal["immediate_retry", "delayed_retry",
                       "alternate_rail", "notify_user", "no_retry"]
    stop_condition: str
    expected_recovery_rate: float
```

### Default policy table (constants in `src/retry_policy.py`)

| Cause | max_attempts | intervals_seconds | strategy | expected_recovery_rate |
|---|---|---|---|---|
| BANK_TIMEOUT | 3 | [30, 300, 3600] | immediate_retry | 0.65 |
| INSUFFICIENT_BALANCE | 1 | [86400] | delayed_retry | 0.35 |
| MANDATE_ERROR | 0 | [] | notify_user | 0.10 |
| NETWORK_ERROR | 3 | [10, 60, 300] | immediate_retry | 0.85 |
| LIMIT_EXCEEDED | 1 | [86400] | delayed_retry | 0.50 |
| UNKNOWN | 1 | [60] | notify_user | 0.15 |

Stopping rules on top:
- Global cost cap: $0.10 per transaction
- Global time window: 24 hours
- Attempts cap: max_attempts per policy

### AuditEntry
```python
class AuditEntry(BaseModel):
    entry_id: str
    txn_id: str
    timestamp: datetime
    stage: Literal["enriched", "classified", "policy_selected",
                   "retry_attempted", "recovered", "abandoned"]
    tier_used: Optional[str]        # "keyword" | "embedding" | "gemini" | "groq" | None
    llm_provider_used: Optional[str]
    llm_latency_ms: Optional[int]
    input_snapshot: dict
    output_snapshot: dict
    reasoning: str
    cost_estimate_usd: Optional[float]
```

---

## 9. REPO STRUCTURE

```
upi-payment-recovery-agent/
├── AGENTS.md                    # this file (source of truth)
├── CLAUDE.md                    # symlink to AGENTS.md (copy on Windows if symlink fails)
├── README.md
├── requirements.txt              # pinned versions
├── .env.example                  # template, no real keys
├── .gitignore                    # ignore .env, logs/*.jsonl, __pycache__, .venv
├── LICENSE                       # MIT
├── app.py                        # Streamlit UI entry point
├── src/
│   ├── __init__.py
│   ├── models.py                 # pydantic schemas
│   ├── data_generator.py          # generates data/synthetic_transactions.json
│   ├── preprocessing.py           # regex extraction (VPA, error codes)
│   ├── classifier.py               # 4-tier cascade orchestrator
│   ├── tier_keyword.py             # Tier 1
│   ├── tier_embedding.py           # Tier 2 (sentence-transformers)
│   ├── llm_client.py               # Tier 3 + 4 (Gemini + Groq)
│   ├── retry_policy.py             # deterministic policy lookup + stopping rules
│   ├── recovery_agent.py           # async orchestrator
│   ├── audit_log.py                 # append-only JSONL
│   └── metrics.py                   # recovery rate, F1, cost, tier distribution
├── data/
│   ├── synthetic_transactions.json  # 200 records, generated
│   └── labeled_examples.json        # 90 labeled messages for Tier 2
├── tests/
│   ├── __init__.py
│   ├── test_preprocessing.py
│   ├── test_tier_keyword.py
│   ├── test_tier_embedding.py
│   ├── test_llm_fallback.py
│   ├── test_retry_policy.py
│   └── test_recovery_agent.py
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DECISIONS.md
│   ├── FAILURE_LOG.md
│   └── ROADMAP.md
└── logs/
    └── .gitkeep                     # audit.jsonl generated at runtime (gitignored)
```

---

## 10. ELEVEN-PHASE EXECUTION PLAN

Pause at the end of every phase. Wait for explicit approval before proceeding. Do not
stack unproven code.

**Phase 0: Environment check (target 15 min)**
- Verify Python 3.12 (downgrade from 3.14 if needed) — actual: 3.13.14, approved deviation
- Verify git installed and configured (user.name, user.email)
- Verify Chandan has ROTATED Gemini and Groq API keys ready in .env
- Verify GitHub account and can push public repo
- ~~Verify Chandan is on Omarchy (Arch Linux)~~ — actual: Windows 11, approved deviation

**Phase 1: Scaffold (target 45 min)**
- Full folder structure
- requirements.txt: google-genai, groq, sentence-transformers, pydantic, streamlit,
  python-dotenv, pytest, faker
- .env.example, .gitignore, README stub
- git init, first commit, push to public GitHub
- Create AGENTS.md at root, symlink CLAUDE.md to AGENTS.md
- Approval gate: `pip install -r requirements.txt` runs cleanly in a fresh venv.

**Phase 2: Models + data generator (target 90 min)**
- src/models.py (all pydantic schemas)
- src/data_generator.py using faker for Indian merchant names, UPI VPAs, bank
  codes, realistic error message patterns per RootCause
- Realistic distribution: bias toward BANK_TIMEOUT and NETWORK_ERROR
- tests/test_data_generator.py: schema compliance, distribution check
- Approval gate: `python -m src.data_generator` writes 200 valid records.

**Phase 3: Async LLM client (target 90 min)**
- src/llm_client.py with async LLMClient class
- Gemini primary path with JSON mode
- Groq fallback on Gemini error/timeout/rate-limit
- Latency and cost tracking per call
- tests/test_llm_fallback.py with mocked Gemini failures
- Approval gate: mocked fallback test passes.

**Phase 3.5: Embedding tier (target 120 min)**
- src/tier_embedding.py
- Load all-MiniLM-L6-v2 once at startup
- data/labeled_examples.json with 15 examples per RootCause bucket
- Compute embeddings for all labeled examples at startup, cache in memory
- kNN classification with cosine threshold > 0.75
- Approval gate: `python -c "from src.tier_embedding import classify; print(classify('insufficient balance in account'))"` returns INSUFFICIENT_BALANCE.

**Phase 4: Full cascade + retry policy (target 120 min)**
- src/preprocessing.py (regex extraction)
- src/tier_keyword.py (dictionary lookup)
- src/classifier.py (orchestrator that runs preprocessing then Tier 1, 2, 3, 4 in
  cascade)
- src/retry_policy.py (constants table + stopping rules)
- Approval gate: single-transaction end-to-end test through full cascade produces
  expected output.

**Phase 5: Recovery agent + audit log (target 90 min)**
- src/audit_log.py (append-only JSONL, thread-safe)
- src/recovery_agent.py (async orchestrator using asyncio.gather)
- Simulate retry success/failure using expected_recovery_rate per policy
- Approval gate: `python -m src.recovery_agent` runs full batch of 200 in under 2
  minutes, produces logs/audit.jsonl.

**Phase 6: Metrics (target 60 min)**
- src/metrics.py
- Overall and per-bucket recovery rate
- Classification confusion matrix and F1
- Tier routing distribution (actual % per tier, THIS is critical for panel)
- Cost per recovery, fallback rate, stopping rule counts
- Approval gate: metrics dashboard shows numbers that make sense.

**Phase 7: Streamlit UI (target 150 min)**
- app.py single file
- Tabs: Metrics, Transactions Table, Drilldown, Random Failures
- Random Failures button: reads audit.jsonl, filters stage='abandoned',
  random.sample(5), displays with full trace (anti-cherry-picking)
- Approval gate: `streamlit run app.py` opens local demo. All 4 tabs work.

**Phase 8: Deploy to Streamlit Cloud (target 30 min)**
- Push to GitHub
- share.streamlit.io -> connect repo
- Add GEMINI_API_KEY, GROQ_API_KEY as secrets
- Verify public URL from incognito
- Approval gate: public URL loads and batch runs from a different device.

**Phase 9: Docs (target 90 min)**
- README.md (use template in Section 12)
- docs/ARCHITECTURE.md
- docs/DECISIONS.md (ADR-style)
- docs/FAILURE_LOG.md (minimum 3 real failures)
- docs/ROADMAP.md (6-month vision, panel Q6)

**Phase 10: Video (target 90 min)**
- 5-minute video, hit exact time marks. Section 14 has the script.

**Phase 11: Form submission (target 30 min)**
- Section 15 has the answers. Verify all URLs in incognito before submitting.

Total: ~14.5 hours. Zero margin. Skip pauses if a phase runs long.

---

## 11. PANEL PREP: PREPARED ANSWERS

**Q1: "Walk me through your architecture decisions"**

"Linear pipeline. Ingestion produces synthetic failed transactions. Recovery agent
orchestrator runs each through preprocessing, then a 4-tier classifier cascade, then
policy selection, then retry simulation, then audit log. Single Streamlit app for demo.

Streamlit because the demo is the UI. No production backend needed.

JSONL over database because 200 records don't need one. Grep-able, portable,
survives partial writes.

pydantic v2 because LLM outputs drift. Catches at parse time."

**Q2: "What happens when the LLM API fails?"**

"The LLM client wraps Gemini primary and Groq fallback. On timeout, rate-limit, or 5xx
from Gemini, the client automatically retries the same request against Groq. Audit log
records which provider handled each call. If both fail, the transaction defaults to
UNKNOWN and routes to notify_user policy. The batch never crashes, individual
transactions degrade gracefully."

**Q3: "Why AI here and not rule-based?"**

"The LLM processes only around 15 percent of my transactions in this batch. 85
percent are classified locally using regex enrichment, keyword matching, and a
lightweight 80MB embedding model, all in milliseconds and at zero cost. The LLM is
expensive and slow, so it is my last resort for novel or ambiguous messages that the
cheaper tiers cannot handle. That is the right tool in the right place, and here is where I
chose not to use one."

**Q4: "Show me a case where your system fails"**

Pull a specific failing txn_id from audit log in drilldown UI.

Template: "Here is TXN-047. The raw error was 'PSP down for maintenance for 4 hours.'
Classifier tagged as NETWORK_ERROR, triggered 3 immediate retries at 10, 60, 300
seconds. All 3 failed because the PSP was still down. Policy caps NETWORK_ERROR at
3 attempts within 5 minutes, so marked abandoned. Should have been recognized as a
scheduled outage and routed to delayed retry after 4 hours. Fix would be adding a
duration-extraction step to the classifier."

**Q5: "How would you scale this to 10x volume?"**

"Currently pure Python with asyncio because network I/O dominates. If we scaled to
10,000 transactions per second at peak, matching real fintech order-of-magnitude load,
I would rewrite the embedding hot-loop and orchestration layer in C++ or Rust to drop
CPU overhead. For this batch of 200, Python's async capabilities were the right tool, and
I measured the tradeoff."

**Q6: "What would you build next if you had 6 months?"**

"Four directions.

First, integrate with real Razorpay test-mode APIs instead of synthetic data. Would
validate whether my synthetic distribution matches real failure patterns.

Second, add a learning loop. Retry policies are static tables from NPCI baseline. Given
real historical outcomes, build a per-merchant recovery model that updates policy
parameters from actual patterns.

Third, run the classifier and audit log inside a TEE like AWS Nitro Enclaves. Merchant
payment data is PII and needs verifiable inference guarantees. Current version uses
synthetic data so TEE would have been overhead, but I have a design sketch.

Fourth, extend interventions beyond retries. WhatsApp nudges for insufficient-balance,
alternate rail suggestions when UPI fails, promise-to-pay flows for B2B receivables."

---

## 12. README.md TEMPLATE

See README.md at repo root. Fill numbers in after Phase 6.

---

## 13. FAILURE_LOG.md TEMPLATE

Fill in real failures. Do not fabricate. Mundane failures count.

```
# Failure Log

## FAILURE 1: [YYYY-MM-DD] [short title]

**What happened:**
**Impact:**
**Fix:**
**Measured improvement:**
**Still unsolved:**

## FAILURE 2: ...

## FAILURE 3: ...
```

Aim for minimum 3 real failures. A pinned-version issue counts. A pydantic validation
error that took an hour to debug counts. A silent async bug counts.

---

## 14. VIDEO SCRIPT (5 minutes)

**0:00 to 0:30 — Problem**
Slide with the 4-6% NPCI failure rate stat. "Indian UPI merchants lose 4-6% of revenue to
payment failures. Most recovery today is naive retries or nothing. I built the UPI
Payment Failure Recovery Agent to close the loop."

**0:30 to 2:30 — Live demo**
Screen-record Streamlit UI. Click Run Batch. Show metrics dashboard. Show tier
distribution (85% classified locally, 15% via LLM). Click into one transaction. Show full
audit trail. Show Random Failures button to prove no cherry-picking.

**2:30 to 3:30 — Architecture**
Show cascade diagram. "Preprocessing enriches every transaction. Then 4 tiers:
keyword handles the bulk, embedding handles semantic matches, Gemini handles novel
messages, Groq is emergency fallback. LLM runs on only 15% of traffic. That is the right
tool in the right place."

**3:30 to 4:30 — Results**
Numbers table. Recovery rate per bucket. Tier distribution. Cost. Fallback rate. Main
failure mode with a specific example.

**4:30 to 5:00 — Limitations + next steps**
3 limitations. 3 next steps. "Thanks. Repo link in description."

Record with OBS. YouTube unlisted upload.

---

## 15. FORM FILL ANSWERS

- **Full Name:** Chandan's real full name
- **College:** Cambridge Institute of Technology, Bengaluru
- **Graduation Year:** 2028
- **Bangalore Availability:** Yes
- **Duration:** 6 months
- **Selected Track:** Track 3: AI Revenue Recovery
- **Project Name:** UPI Payment Failure Recovery Agent

**Project Objectives (2-3 sentences):**

"Indian merchants lose 4-6% of UPI transaction revenue to payment failures that could
be recovered with root-cause-aware retry strategies. This agent uses a 4-tier cascade
(regex, keyword match, local embedding, LLM) to classify each failure with LLM as last
resort, then routes to a deterministic retry policy with bounded stopping rules. Tested
on 200 synthetic transactions, achieving [X]% overall recovery with 85% of
classifications handled locally at zero cost."

**Build Challenges (fill actual numbers after Phase 6):**

"Challenge 1: Initial Gemini prompt returned category labels not in my RootCause enum
(e.g., 'card_declined' when correct bucket was INSUFFICIENT_BALANCE). Switched to
JSON mode with enum values injected into the prompt and pydantic v2 parsing on the
response. Classification accuracy on hand-labeled test set went from [X]% to [Y]%.

Challenge 2: Gemini rate-limited during concurrent batch runs. Added Groq as
automatic fallback via wrapper in llm_client.py. Currently [Z]% of calls route to Groq
depending on Gemini load.

Challenge 3 (Remaining): Synthetic data has clean bank_code fields. Real production
data would need bank inference from the UPI VPA suffix (@ybl, @paytm, @okhdfcbank,
etc.)."

---

## 16. HANDOFF RULES

- **Do not add features not in this spec without asking Chandan.** Scope creep kills
  15hr builds.
- **When creating files, produce the complete file.** No partial diffs.
- **When a design decision comes up this spec doesn't cover, propose 2-3 options and
  wait.** Do not decide unilaterally.
- **Test each module before moving to next phase.** Do not stack unproven code.
- **Commit frequently.** Small commits, clear messages.
- **When something breaks, add it to docs/FAILURE_LOG.md BEFORE fixing.**
- **All measured claims must be actually measured.** Replace "targeted at X%" with real
  numbers after Phase 6.
- **Run under virtualenv.** Never install into system Python.

---

## 17. FIRST ACTION

Read this file completely. Then execute Phase 0. Ask Chandan for:
1. Python version output (`python --version`, need 3.12)
2. Confirmation both API keys are rotated and ready
3. GitHub username and preferred repo name (default: `upi-payment-recovery-agent`)

Then proceed to environment verification. Do not ask for approval on the overall plan,
only on individual phase gates.

END OF SPEC.
