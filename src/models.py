"""Pydantic schemas shared across the recovery pipeline."""

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel


class RootCause(str, Enum):
    BANK_TIMEOUT = "bank_timeout"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    MANDATE_ERROR = "mandate_error"
    NETWORK_ERROR = "network_error"
    LIMIT_EXCEEDED = "limit_exceeded"
    UNKNOWN = "unknown"


class Transaction(BaseModel):
    txn_id: str
    merchant_id: str
    amount_inr: float
    upi_vpa: str
    timestamp: datetime
    status: Literal["failed"]
    raw_error_message: str
    bank_code: str
    metadata: dict = {}


class RetryPolicy(BaseModel):
    cause: RootCause
    max_attempts: int
    intervals_seconds: list[int]
    strategy: Literal[
        "immediate_retry", "delayed_retry", "alternate_rail", "notify_user", "no_retry"
    ]
    stop_condition: str
    expected_recovery_rate: float


class AuditEntry(BaseModel):
    entry_id: str
    txn_id: str
    timestamp: datetime
    stage: Literal[
        "enriched", "classified", "policy_selected", "retry_attempted", "recovered", "abandoned"
    ]
    tier_used: Optional[str] = None
    llm_provider_used: Optional[str] = None
    llm_latency_ms: Optional[int] = None
    input_snapshot: dict
    output_snapshot: dict
    reasoning: str
    cost_estimate_usd: Optional[float] = None
