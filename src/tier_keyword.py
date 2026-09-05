"""Tier 1: keyword pattern match. Cheapest, fastest, first tier in the cascade."""

from src.models import RootCause

# order matters: checked top to bottom, first match wins
KEYWORDS: list[tuple[RootCause, list[str]]] = [
    (RootCause.MANDATE_ERROR, ["mandate", "nach", "e-mandate"]),
    (RootCause.INSUFFICIENT_BALANCE, ["insufficient", "low balance", "not enough", "funds too low", "lacks sufficient"]),
    (RootCause.LIMIT_EXCEEDED, ["limit exceeded", "cap reached", "limit reached", "exceeds allowed", "limit breached", "cap exhausted", "velocity limit"]),
    (RootCause.NETWORK_ERROR, ["network", "connection reset", "psp down", "maintenance", "switch unreachable", "socket", "outage", "connectivity", "packet loss", "vpn", "routing failure"]),
    (RootCause.BANK_TIMEOUT, ["timeout", "timed out", "unreachable", "not responding", "no response", "did not respond"]),
]


def classify(error_message: str) -> RootCause | None:
    """Returns a RootCause on a keyword hit, else None to escalate to Tier 2."""
    lowered = error_message.lower()
    for root_cause, keywords in KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return root_cause
    return None
