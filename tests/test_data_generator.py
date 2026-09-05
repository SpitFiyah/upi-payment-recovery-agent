from collections import Counter

from src.data_generator import generate_batch
from src.models import RootCause, Transaction


def test_generate_batch_schema_compliance():
    batch = generate_batch(50)
    assert len(batch) == 50
    for txn in batch:
        assert isinstance(txn, Transaction)
        assert txn.status == "failed"
        assert 100.0 <= txn.amount_inr <= 50000.0
        assert "@" in txn.upi_vpa
        assert txn.bank_code
        assert txn.metadata["true_root_cause"] in [c.value for c in RootCause]


def test_generate_batch_distribution_biased_toward_timeout_and_network():
    batch = generate_batch(200)
    counts = Counter(t.metadata["true_root_cause"] for t in batch)
    assert counts[RootCause.BANK_TIMEOUT.value] > counts[RootCause.MANDATE_ERROR.value]
    assert counts[RootCause.NETWORK_ERROR.value] > counts[RootCause.UNKNOWN.value]
