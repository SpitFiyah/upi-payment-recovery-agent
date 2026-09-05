from src.models import RootCause
from src.tier_keyword import classify


def test_insufficient_balance_keyword():
    assert classify("Insufficient balance in account") == RootCause.INSUFFICIENT_BALANCE


def test_bank_timeout_keyword():
    assert classify("Bank server timeout, please try again") == RootCause.BANK_TIMEOUT


def test_limit_exceeded_keyword():
    assert classify("Daily transaction limit exceeded") == RootCause.LIMIT_EXCEEDED


def test_mandate_error_keyword():
    assert classify("Mandate not found for this transaction") == RootCause.MANDATE_ERROR


def test_network_error_keyword():
    assert classify("Network error, connection reset by peer") == RootCause.NETWORK_ERROR


def test_no_keyword_match_escalates():
    assert classify("PSP returned malformed response") is None
