"""Computes recovery, classification, and cost metrics from the audit log.

Cross-references audit.jsonl against the original synthetic transactions
(which carry a ground-truth true_root_cause in metadata) to get a real
confusion matrix and F1, not just self-reported accuracy.
"""

import json
from collections import Counter, defaultdict

from src.audit_log import read_all
from src.models import AuditEntry, RootCause
from src.recovery_agent import load_transactions
from src.retry_policy import GLOBAL_TIME_WINDOW_SECONDS, get_policy

ALL_CAUSES = [c.value for c in RootCause]


def _compute_macro_f1(confusion: Counter) -> tuple[float, dict[str, float]]:
    per_class_f1: dict[str, float] = {}
    for cause in ALL_CAUSES:
        tp = confusion.get((cause, cause), 0)
        fp = sum(c for (t, p), c in confusion.items() if p == cause and t != cause)
        fn = sum(c for (t, p), c in confusion.items() if t == cause and p != cause)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_class_f1[cause] = f1
    macro_f1 = sum(per_class_f1.values()) / len(per_class_f1)
    return macro_f1, per_class_f1


def compute_metrics() -> dict:
    transactions = {t.txn_id: t for t in load_transactions()}
    entries = read_all()

    by_txn: dict[str, list[AuditEntry]] = defaultdict(list)
    for e in entries:
        by_txn[e.txn_id].append(e)

    total = len(by_txn)
    recovered_count = 0
    per_bucket_total: Counter = Counter()
    per_bucket_recovered: Counter = Counter()
    tier_counts: Counter = Counter()
    cost_total = 0.0
    llm_provider_counts: Counter = Counter()
    stop_reason_counts: Counter = Counter()
    confusion: Counter = Counter()  # keyed by (true_cause, predicted_cause)

    for txn_id, txn_entries in by_txn.items():
        txn = transactions[txn_id]
        true_cause = txn.metadata.get("true_root_cause", "unknown")

        classified_entry = next(e for e in txn_entries if e.stage == "classified")
        predicted_cause = classified_entry.output_snapshot["root_cause"]
        tier_counts[classified_entry.tier_used] += 1
        cost_total += classified_entry.cost_estimate_usd or 0.0
        if classified_entry.llm_provider_used:
            llm_provider_counts[classified_entry.llm_provider_used] += 1

        confusion[(true_cause, predicted_cause)] += 1
        per_bucket_total[predicted_cause] += 1

        final_entry = txn_entries[-1]
        if final_entry.stage == "recovered":
            recovered_count += 1
            per_bucket_recovered[predicted_cause] += 1
        else:
            policy = get_policy(RootCause(predicted_cause))
            retry_entries = [e for e in txn_entries if e.stage == "retry_attempted"]
            if policy.max_attempts == 0:
                stop_reason_counts["no_retry_policy"] += 1
            elif retry_entries:
                last = retry_entries[-1]
                attempt_number = last.input_snapshot.get("attempt_number", 0)
                elapsed = last.input_snapshot.get("elapsed_seconds", 0)
                if elapsed >= GLOBAL_TIME_WINDOW_SECONDS:
                    stop_reason_counts["time_window"] += 1
                elif attempt_number >= policy.max_attempts:
                    stop_reason_counts["attempts_cap"] += 1
                else:
                    stop_reason_counts["unknown"] += 1
            else:
                stop_reason_counts["unknown"] += 1

    overall_recovery_rate = recovered_count / total if total else 0.0
    per_bucket_recovery_rate = {
        cause: per_bucket_recovered[cause] / per_bucket_total[cause] for cause in per_bucket_total
    }
    tier_distribution = {
        (tier if tier else "none"): count / total for tier, count in tier_counts.items()
    }

    gemini_calls = llm_provider_counts.get("gemini", 0)
    groq_calls = llm_provider_counts.get("groq", 0)
    llm_calls = gemini_calls + groq_calls
    fallback_rate = groq_calls / llm_calls if llm_calls else 0.0
    cost_per_recovery = cost_total / recovered_count if recovered_count else 0.0

    macro_f1, per_class_f1 = _compute_macro_f1(confusion)

    return {
        "total_transactions": total,
        "overall_recovery_rate": overall_recovery_rate,
        "per_bucket_recovery_rate": per_bucket_recovery_rate,
        "tier_distribution": tier_distribution,
        "cost_total_usd": round(cost_total, 6),
        "cost_per_recovery_usd": round(cost_per_recovery, 6),
        "fallback_rate": fallback_rate,
        "stopping_rule_counts": dict(stop_reason_counts),
        "macro_f1": macro_f1,
        "per_class_f1": per_class_f1,
        "confusion_matrix": {f"{t}->{p}": c for (t, p), c in confusion.items()},
    }


if __name__ == "__main__":
    print(json.dumps(compute_metrics(), indent=2))
