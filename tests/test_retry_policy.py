from src.models import RootCause
from src.retry_policy import GLOBAL_COST_CAP_USD, GLOBAL_TIME_WINDOW_SECONDS, get_policy, should_stop


def test_get_policy_returns_expected_strategy():
    assert get_policy(RootCause.NETWORK_ERROR).strategy == "immediate_retry"
    assert get_policy(RootCause.MANDATE_ERROR).strategy == "notify_user"
    assert get_policy(RootCause.MANDATE_ERROR).max_attempts == 0


def test_should_stop_on_max_attempts():
    policy = get_policy(RootCause.BANK_TIMEOUT)
    assert should_stop(attempt_number=3, elapsed_seconds=10, cost_so_far_usd=0.0, policy=policy)
    assert not should_stop(attempt_number=1, elapsed_seconds=10, cost_so_far_usd=0.0, policy=policy)


def test_should_stop_on_time_window():
    policy = get_policy(RootCause.NETWORK_ERROR)
    assert should_stop(
        attempt_number=0, elapsed_seconds=GLOBAL_TIME_WINDOW_SECONDS, cost_so_far_usd=0.0, policy=policy
    )


def test_should_stop_on_cost_cap():
    policy = get_policy(RootCause.NETWORK_ERROR)
    assert should_stop(
        attempt_number=0, elapsed_seconds=1, cost_so_far_usd=GLOBAL_COST_CAP_USD, policy=policy
    )


def test_mandate_error_stops_immediately_zero_attempts():
    policy = get_policy(RootCause.MANDATE_ERROR)
    assert should_stop(attempt_number=0, elapsed_seconds=0, cost_so_far_usd=0.0, policy=policy)
