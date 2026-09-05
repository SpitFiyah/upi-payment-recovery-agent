"""Async orchestrator: runs a batch of failed transactions through the full
recovery pipeline (classify, select policy, simulate retries) and writes every
decision to the audit log.

Retry simulation note: expected_recovery_rate is applied as a per-attempt
Bernoulli probability, and at least one simulated attempt always runs even
for notify_user/no_retry policies (max_attempts=0), representing the chance
the transaction resolves through that channel (e.g. the user fixes their
mandate on their own). This is the simplest read of the spec's requirement
that recovery rate be measured per bucket, since a policy with zero attempts
would otherwise always show 0% regardless of its configured recovery rate.
"""

import asyncio
import json
import random
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from src import classifier
from src.audit_log import append
from src.llm_client import LLMClient
from src.models import AuditEntry, Transaction
from src.retry_policy import get_policy

MAX_CONCURRENT_LLM_CALLS = 10
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "synthetic_transactions.json"


def _new_entry_id() -> str:
    return str(uuid.uuid4())


async def process_transaction(
    transaction: Transaction, llm_client: LLMClient, semaphore: asyncio.Semaphore
) -> None:
    async with semaphore:
        enriched, result = await classifier.classify(transaction, llm_client)

    append(
        AuditEntry(
            entry_id=_new_entry_id(),
            txn_id=transaction.txn_id,
            timestamp=datetime.now(),
            stage="enriched",
            tier_used=None,
            llm_provider_used=None,
            llm_latency_ms=None,
            input_snapshot={"upi_vpa": transaction.upi_vpa, "raw_error_message": transaction.raw_error_message},
            output_snapshot={"bank_code": enriched.bank_code, "metadata": enriched.metadata},
            reasoning="Preprocessing extracted bank code and any embedded error code",
            cost_estimate_usd=0.0,
        )
    )

    is_llm_tier = result.tier_used in ("gemini", "groq")
    append(
        AuditEntry(
            entry_id=_new_entry_id(),
            txn_id=transaction.txn_id,
            timestamp=datetime.now(),
            stage="classified",
            tier_used=result.tier_used,
            llm_provider_used=result.tier_used if is_llm_tier else None,
            llm_latency_ms=result.latency_ms if is_llm_tier else None,
            input_snapshot={"raw_error_message": enriched.raw_error_message},
            output_snapshot={"root_cause": result.root_cause.value},
            reasoning=result.reasoning,
            cost_estimate_usd=result.cost_estimate_usd,
        )
    )

    policy = get_policy(result.root_cause)
    append(
        AuditEntry(
            entry_id=_new_entry_id(),
            txn_id=transaction.txn_id,
            timestamp=datetime.now(),
            stage="policy_selected",
            tier_used=None,
            llm_provider_used=None,
            llm_latency_ms=None,
            input_snapshot={"root_cause": result.root_cause.value},
            output_snapshot={
                "strategy": policy.strategy,
                "max_attempts": policy.max_attempts,
                "expected_recovery_rate": policy.expected_recovery_rate,
            },
            reasoning=f"Selected {policy.strategy} for {result.root_cause.value}",
            cost_estimate_usd=0.0,
        )
    )

    attempts_to_simulate = max(policy.max_attempts, 1)
    recovered = False
    for attempt_number in range(1, attempts_to_simulate + 1):
        success = random.random() < policy.expected_recovery_rate
        append(
            AuditEntry(
                entry_id=_new_entry_id(),
                txn_id=transaction.txn_id,
                timestamp=datetime.now(),
                stage="retry_attempted",
                tier_used=None,
                llm_provider_used=None,
                llm_latency_ms=None,
                input_snapshot={"attempt_number": attempt_number, "strategy": policy.strategy},
                output_snapshot={"success": success},
                reasoning=f"Simulated attempt {attempt_number}/{attempts_to_simulate}, success={success}",
                cost_estimate_usd=0.0,
            )
        )
        if success:
            recovered = True
            break

    final_stage = "recovered" if recovered else "abandoned"
    append(
        AuditEntry(
            entry_id=_new_entry_id(),
            txn_id=transaction.txn_id,
            timestamp=datetime.now(),
            stage=final_stage,
            tier_used=None,
            llm_provider_used=None,
            llm_latency_ms=None,
            input_snapshot={"root_cause": result.root_cause.value},
            output_snapshot={"recovered": recovered},
            reasoning=f"Transaction {final_stage} after {attempts_to_simulate} simulated attempt(s)",
            cost_estimate_usd=0.0,
        )
    )


async def run_batch(transactions: list[Transaction]) -> None:
    llm_client = LLMClient()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)
    await asyncio.gather(
        *(process_transaction(txn, llm_client, semaphore) for txn in transactions)
    )


def load_transactions() -> list[Transaction]:
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return [Transaction.model_validate(t) for t in raw]


async def main() -> None:
    load_dotenv()
    random.seed(7)
    if Path("logs/audit.jsonl").exists():
        Path("logs/audit.jsonl").unlink()
    transactions = load_transactions()
    start = asyncio.get_event_loop().time()
    await run_batch(transactions)
    elapsed = asyncio.get_event_loop().time() - start
    print(f"Processed {len(transactions)} transactions in {elapsed:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
