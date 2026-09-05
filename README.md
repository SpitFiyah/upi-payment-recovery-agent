# UPI Payment Failure Recovery Agent

Track 3 submission for the Razorpay AI Buildathon 2026.

Detects UPI payment failures, classifies root cause via a multi-tier
cascade with LLM as last resort, executes a bounded retry strategy with
deterministic stopping rules, and reports measured recovery across a
batch with full audit trail.

**Live demo:** Pending Streamlit Cloud deploy (needs a browser-based GitHub OAuth step, see Setup below to run locally in the meantime)
**Video pitch:** TBD

## What this does

Indian merchants using UPI experience 4-6% payment failure rates
publicly reported by NPCI. Most retry logic in production is either
naive fixed-interval or nothing. This agent closes the recovery loop:

1. Preprocessing enriches every transaction with bank code from UPI VPA
2. 4-tier cascade classifies root cause: keyword match, then local
   embedding, then Gemini, then Groq fallback
3. Deterministic policy selects retry strategy based on cause
4. Bounded retry loop respects stopping rules (max attempts, cost cap,
   time window)
5. Every decision logged to append-only JSONL audit trail
6. Metrics dashboard shows recovery rate, classification accuracy, cost
   per recovery, tier routing distribution

## Measured results on 200 synthetic transactions

| Metric | Value |
|---|---|
| Overall recovery rate | 71.0% |
| Classification macro-F1 | 0.959 |
| Tier distribution (keyword / embedding / LLM) | 76.5% / 13.5% / 10% |
| Cost per batch (LLM API) | $0.00 (all 10% of LLM-tier traffic landed on Groq's free tier this run, see below) |
| Groq fallback rate | 100% of LLM-tier calls this run |
| Avg batch time | 11-23 seconds for all 200 transactions |

The 100% Groq fallback rate is not a bug, Gemini failed on every LLM-tier
call in every full batch run so far despite working fine in isolated single
calls, most likely a free-tier quota ceiling on the key used tonight. Full
detail in [docs/FAILURE_LOG.md](docs/FAILURE_LOG.md), Failure 4. The tier
split (76.5/13.5/10) is also not the 60/25/15 originally targeted, the
synthetic data ended up easier for the deterministic tiers than planned.
Both numbers are what actually happened, not what was targeted, per this
project's own rule that measured claims have to be measured.

Full breakdown in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Setup (under 10 minutes)

Prerequisites: Python 3.12+, git.

    git clone https://github.com/SpitFiyah/upi-payment-recovery-agent.git
    cd upi-payment-recovery-agent
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    copy .env.example .env
    python -m src.data_generator
    streamlit run app.py

Then click "Run Batch" inside the app to populate the audit log and metrics.

Free API keys:
- Gemini: https://aistudio.google.com
- Groq: https://console.groq.com

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Known limitations

See [docs/FAILURE_LOG.md](docs/FAILURE_LOG.md).

## License

MIT
