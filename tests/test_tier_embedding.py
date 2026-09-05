from src.models import RootCause
from src.tier_embedding import classify


def test_classifies_paraphrased_insufficient_balance():
    assert classify("insufficient balance in account") == RootCause.INSUFFICIENT_BALANCE


def test_classifies_paraphrased_bank_timeout():
    assert classify("bank server took too long and did not respond") == RootCause.BANK_TIMEOUT


def test_escalates_on_unrelated_text():
    assert classify("completely unrelated gibberish about weather forecast") is None
