"""Deterministic retry policy lookup and stopping rules."""

from src.models import RetryPolicy, RootCause

GLOBAL_COST_CAP_USD = 0.10
GLOBAL_TIME_WINDOW_SECONDS = 24 * 3600

POLICIES: dict[RootCause, RetryPolicy] = {
    RootCause.BANK_TIMEOUT: RetryPolicy(
        cause=RootCause.BANK_TIMEOUT,
        max_attempts=3,
        intervals_seconds=[30, 300, 3600],
        strategy="immediate_retry",
        stop_condition="stop after 3 attempts, 24h window, or $0.10 cost cap",
        expected_recovery_rate=0.65,
    ),
    RootCause.INSUFFICIENT_BALANCE: RetryPolicy(
        cause=RootCause.INSUFFICIENT_BALANCE,
        max_attempts=1,
        intervals_seconds=[86400],
        strategy="delayed_retry",
        stop_condition="single retry after 24h, then abandon",
        expected_recovery_rate=0.35,
    ),
    RootCause.MANDATE_ERROR: RetryPolicy(
        cause=RootCause.MANDATE_ERROR,
        max_attempts=0,
        intervals_seconds=[],
        strategy="notify_user",
        stop_condition="no retry, mandate needs user action",
        expected_recovery_rate=0.10,
    ),
    RootCause.NETWORK_ERROR: RetryPolicy(
        cause=RootCause.NETWORK_ERROR,
        max_attempts=3,
        intervals_seconds=[10, 60, 300],
        strategy="immediate_retry",
        stop_condition="stop after 3 attempts, 24h window, or $0.10 cost cap",
        expected_recovery_rate=0.85,
    ),
    RootCause.LIMIT_EXCEEDED: RetryPolicy(
        cause=RootCause.LIMIT_EXCEEDED,
        max_attempts=1,
        intervals_seconds=[86400],
        strategy="delayed_retry",
        stop_condition="single retry after 24h once limit window resets",
        expected_recovery_rate=0.50,
    ),
    RootCause.UNKNOWN: RetryPolicy(
        cause=RootCause.UNKNOWN,
        max_attempts=1,
        intervals_seconds=[60],
        strategy="notify_user",
        stop_condition="single retry after 60s, then notify user",
        expected_recovery_rate=0.15,
    ),
}


def get_policy(cause: RootCause) -> RetryPolicy:
    return POLICIES[cause]


def should_stop(
    attempt_number: int, elapsed_seconds: float, cost_so_far_usd: float, policy: RetryPolicy
) -> bool:
    """True if any stopping rule is triggered: attempts cap, time window, or cost cap."""
    if attempt_number >= policy.max_attempts:
        return True
    if elapsed_seconds >= GLOBAL_TIME_WINDOW_SECONDS:
        return True
    if cost_so_far_usd >= GLOBAL_COST_CAP_USD:
        return True
    return False
