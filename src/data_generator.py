"""Generates synthetic failed UPI transactions for data/synthetic_transactions.json.

Distribution is biased toward BANK_TIMEOUT and NETWORK_ERROR because those are
the most common real-world UPI failure modes per NPCI reporting.
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker

from src.models import RootCause, Transaction
from src.preprocessing import VPA_SUFFIX_TO_BANK_CODE

fake = Faker("en_IN")

BANK_SUFFIXES = list(VPA_SUFFIX_TO_BANK_CODE.keys())

# error message templates per RootCause. Some include an embedded bank error code,
# most do not, matching how upstream messages actually look.
ERROR_TEMPLATES: dict[RootCause, list[str]] = {
    RootCause.BANK_TIMEOUT: [
        "Bank server timeout, please try again",
        "Upstream bank unreachable, request timed out",
        "Transaction timed out waiting for bank response",
        "Bank server not responding (E091)",
        "Gateway timeout from issuing bank",
        "No response from bank within timeout window",
    ],
    RootCause.NETWORK_ERROR: [
        "Network error, connection reset by peer",
        "PSP down for maintenance for 4 hours",
        "Connection to payment switch lost",
        "NPCI network unreachable",
        "Socket timeout communicating with UPI switch",
        "Temporary network glitch, retry recommended",
    ],
    RootCause.INSUFFICIENT_BALANCE: [
        "Insufficient balance in account",
        "Insufficient funds to complete transaction",
        "Available balance too low for this transaction",
        "Transaction declined due to insufficient balance",
    ],
    RootCause.LIMIT_EXCEEDED: [
        "Daily transaction limit exceeded",
        "UPI limit exceeded for this account",
        "Per-transaction limit exceeded (BLR-091)",
        "Monthly UPI cap reached, transaction blocked",
    ],
    RootCause.MANDATE_ERROR: [
        "Mandate not found for this transaction",
        "Mandate expired, cannot process debit",
        "Invalid mandate reference",
        "Mandate revoked by customer",
    ],
    RootCause.UNKNOWN: [
        "Transaction failed due to unspecified error",
        "PSP returned malformed response",
        "Unexpected error code 9999",
        "Processing failed, contact support",
    ],
}

# Phrased differently enough from both the keyword substrings above and the
# labeled examples in data/labeled_examples.json that they clear neither Tier 1
# nor Tier 2 and reach the LLM. Confirmed empirically before wiring these in,
# see FAILURE_LOG for why this was needed: the original templates overlapped
# so heavily with the deterministic tiers that zero transactions ever reached
# the LLM, which undercuts the whole "AI as last resort" architecture.
NOVEL_TEMPLATES: dict[RootCause, list[str]] = {
    RootCause.BANK_TIMEOUT: [
        "Response from partner bank arrived after the acceptable window had already closed",
        "Settlement corridor to this bank is experiencing severe processing lag today",
    ],
    RootCause.NETWORK_ERROR: [
        "Regional data center serving this corridor is experiencing intermittent packet drops of unknown origin",
        "Transaction path between merchant and acquirer is currently degraded",
    ],
    RootCause.INSUFFICIENT_BALANCE: [
        "Debit could not be honored, account holder needs to top up before retrying",
        "Requested amount exceeds what is currently available to move out of this account",
    ],
    RootCause.LIMIT_EXCEEDED: [
        "Risk engine flagged unusually high transaction velocity for this profile and paused further debits",
        "This account has been temporarily capped after unusually frequent transfers today",
    ],
    RootCause.MANDATE_ERROR: [
        "Recurring collection could not proceed, prior consent record appears stale",
        "Standing authorization for this merchant could not be located in bank records",
    ],
    RootCause.UNKNOWN: [
        "Beneficiary account frozen pending KYC review by regulator",
        "Transaction blocked by an internal compliance hold with no further detail provided",
    ],
}

NOVEL_MESSAGE_PROBABILITY = 0.10

# weights bias toward BANK_TIMEOUT and NETWORK_ERROR per spec
ROOT_CAUSE_WEIGHTS = {
    RootCause.BANK_TIMEOUT: 30,
    RootCause.NETWORK_ERROR: 25,
    RootCause.INSUFFICIENT_BALANCE: 20,
    RootCause.LIMIT_EXCEEDED: 12,
    RootCause.MANDATE_ERROR: 8,
    RootCause.UNKNOWN: 5,
}


def _random_vpa() -> str:
    suffix = random.choice(BANK_SUFFIXES)
    username = fake.user_name().replace(".", "").replace("_", "")
    return f"{username}@{suffix}", VPA_SUFFIX_TO_BANK_CODE[suffix]


def generate_transaction() -> Transaction:
    root_cause = random.choices(
        list(ROOT_CAUSE_WEIGHTS.keys()), weights=list(ROOT_CAUSE_WEIGHTS.values())
    )[0]
    if random.random() < NOVEL_MESSAGE_PROBABILITY:
        error_message = random.choice(NOVEL_TEMPLATES[root_cause])
    else:
        error_message = random.choice(ERROR_TEMPLATES[root_cause])
    vpa, bank_code = _random_vpa()
    timestamp = datetime.now() - timedelta(minutes=random.randint(0, 60 * 24 * 7))

    return Transaction(
        txn_id=str(uuid.uuid4()),
        merchant_id=f"MERCH_{random.randint(1, 200):03d}",
        amount_inr=round(random.uniform(100.0, 50000.0), 2),
        upi_vpa=vpa,
        timestamp=timestamp,
        status="failed",
        raw_error_message=error_message,
        bank_code=bank_code,
        metadata={"true_root_cause": root_cause.value},
    )


def generate_batch(count: int = 200) -> list[Transaction]:
    return [generate_transaction() for _ in range(count)]


def main() -> None:
    random.seed(42)
    transactions = generate_batch(200)
    out_path = Path(__file__).resolve().parent.parent / "data" / "synthetic_transactions.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [json.loads(t.model_dump_json()) for t in transactions]
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(transactions)} transactions to {out_path}")


if __name__ == "__main__":
    main()
