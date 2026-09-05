# UPI Payment Failure Recovery Agent

Track 3 submission for the Razorpay AI Buildathon 2026.

Detects UPI payment failures, classifies root cause via a multi-tier
cascade with LLM as last resort, executes a bounded retry strategy with
deterministic stopping rules, and reports measured recovery across a
batch with full audit trail.

**Live demo:** TBD
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

Filled in after Phase 6. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

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

Free API keys:
- Gemini: https://aistudio.google.com
- Groq: https://console.groq.com

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Known limitations

See [docs/FAILURE_LOG.md](docs/FAILURE_LOG.md).

## License

MIT
