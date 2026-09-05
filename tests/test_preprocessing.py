from datetime import datetime

from src.models import Transaction
from src.preprocessing import enrich, extract_bank_code, extract_error_code


def test_extract_bank_code_known_suffixes():
    assert extract_bank_code("someone@ybl") == "YBL"
    assert extract_bank_code("someone@paytm") == "PAYTM"
    assert extract_bank_code("someone@okhdfcbank") == "HDFC"


def test_extract_bank_code_unknown_suffix():
    assert extract_bank_code("someone@unknownbank") == "UNKNOWN"


def test_extract_error_code_hyphenated():
    assert extract_error_code("Per-transaction limit exceeded (BLR-091)") == "BLR-091"


def test_extract_error_code_bare():
    assert extract_error_code("Bank server not responding (E091)") == "E091"


def test_extract_error_code_absent():
    assert extract_error_code("Insufficient balance in account") is None


def _make_txn(vpa: str, error_message: str) -> Transaction:
    return Transaction(
        txn_id="t1",
        merchant_id="MERCH_001",
        amount_inr=500.0,
        upi_vpa=vpa,
        timestamp=datetime.now(),
        status="failed",
        raw_error_message=error_message,
        bank_code="",
        metadata={},
    )


def test_enrich_fills_bank_code_and_error_code():
    txn = _make_txn("someone@oksbi", "Bank server not responding (E091)")
    enriched = enrich(txn)
    assert enriched.bank_code == "SBI"
    assert enriched.metadata["error_code"] == "E091"
    assert txn.bank_code == ""  # original untouched
