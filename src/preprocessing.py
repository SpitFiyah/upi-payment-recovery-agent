"""Preprocessing: regex enrichment that always runs before classification.

Not a classification tier itself. Extracts the bank code from the UPI VPA
suffix and any embedded upstream error code from the raw error message.
"""

import re

from src.models import Transaction

VPA_SUFFIX_TO_BANK_CODE = {
    "ybl": "YBL",
    "paytm": "PAYTM",
    "okhdfcbank": "HDFC",
    "oksbi": "SBI",
    "okicici": "ICICI",
    "okaxis": "AXIS",
    "ibl": "IBL",
}

# matches hyphenated codes like "BLR-091" or bare single-letter codes like "E091"
ERROR_CODE_PATTERN = re.compile(r"[A-Z]{1,4}-\d{2,4}|[A-Z]\d{3,4}")


def extract_bank_code(upi_vpa: str) -> str:
    suffix = upi_vpa.rsplit("@", 1)[-1].lower()
    return VPA_SUFFIX_TO_BANK_CODE.get(suffix, "UNKNOWN")


def extract_error_code(raw_error_message: str) -> str | None:
    match = ERROR_CODE_PATTERN.search(raw_error_message)
    return match.group(0) if match else None


def enrich(transaction: Transaction) -> Transaction:
    """Returns a copy of transaction with bank_code and any error_code filled in."""
    bank_code = extract_bank_code(transaction.upi_vpa)
    error_code = extract_error_code(transaction.raw_error_message)
    updated_metadata = dict(transaction.metadata)
    if error_code:
        updated_metadata["error_code"] = error_code
    return transaction.model_copy(update={"bank_code": bank_code, "metadata": updated_metadata})
