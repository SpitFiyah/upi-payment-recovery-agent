import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src import audit_log, recovery_agent
from src.models import Transaction


@pytest.fixture
def isolated_log(tmp_path, monkeypatch):
    log_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(audit_log, "LOG_PATH", log_path)
    return log_path


@pytest.mark.asyncio
async def test_process_transaction_keyword_hit_writes_full_trace(isolated_log, monkeypatch):
    txn = Transaction(
        txn_id="t1",
        merchant_id="MERCH_001",
        amount_inr=500.0,
        upi_vpa="someone@ybl",
        timestamp=datetime.now(),
        status="failed",
        raw_error_message="Insufficient balance in account",
        bank_code="",
        metadata={},
    )
    llm_client = AsyncMock()
    monkeypatch.setattr(recovery_agent.random, "random", lambda: 0.0)  # force every attempt to succeed

    import asyncio

    await recovery_agent.process_transaction(txn, llm_client, asyncio.Semaphore(1))

    entries = audit_log.read_all()
    stages = [e.stage for e in entries]
    assert stages == ["enriched", "classified", "policy_selected", "retry_attempted", "recovered"]
    assert all(e.txn_id == "t1" for e in entries)
    llm_client.classify.assert_not_called()


@pytest.mark.asyncio
async def test_mandate_error_always_gets_at_least_one_simulated_attempt(isolated_log, monkeypatch):
    txn = Transaction(
        txn_id="t2",
        merchant_id="MERCH_002",
        amount_inr=500.0,
        upi_vpa="someone@ybl",
        timestamp=datetime.now(),
        status="failed",
        raw_error_message="Mandate not found for this transaction",
        bank_code="",
        metadata={},
    )
    llm_client = AsyncMock()
    monkeypatch.setattr(recovery_agent.random, "random", lambda: 0.99)  # force failure

    import asyncio

    await recovery_agent.process_transaction(txn, llm_client, asyncio.Semaphore(1))

    entries = audit_log.read_all()
    retry_entries = [e for e in entries if e.stage == "retry_attempted"]
    assert len(retry_entries) == 1
    assert entries[-1].stage == "abandoned"
