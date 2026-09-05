"""Streamlit UI for the UPI Payment Failure Recovery Agent. This is the entire
frontend and backend, per the project's tech stack decisions, see AGENTS.md
section 7.
"""

import asyncio
import random
from collections import defaultdict

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.audit_log import read_all
from src.metrics import compute_metrics
from src.models import AuditEntry, Transaction
from src.recovery_agent import load_transactions, main as run_recovery_batch

load_dotenv()

st.set_page_config(page_title="UPI Payment Failure Recovery Agent", layout="wide")


@st.cache_data
def _load_data(_cache_bust: int):
    transactions = {t.txn_id: t for t in load_transactions()}
    entries = read_all()
    by_txn: dict[str, list[AuditEntry]] = defaultdict(list)
    for e in entries:
        by_txn[e.txn_id].append(e)
    return transactions, by_txn


def _build_transactions_table(transactions: dict[str, Transaction], by_txn: dict[str, list[AuditEntry]]) -> pd.DataFrame:
    rows = []
    for txn_id, txn in transactions.items():
        txn_entries = by_txn.get(txn_id, [])
        classified = next((e for e in txn_entries if e.stage == "classified"), None)
        final = txn_entries[-1] if txn_entries else None
        rows.append(
            {
                "txn_id": txn_id,
                "merchant_id": txn.merchant_id,
                "amount_inr": txn.amount_inr,
                "upi_vpa": txn.upi_vpa,
                "raw_error_message": txn.raw_error_message,
                "true_root_cause": txn.metadata.get("true_root_cause"),
                "predicted_root_cause": classified.output_snapshot.get("root_cause") if classified else None,
                "tier_used": classified.tier_used if classified else None,
                "final_stage": final.stage if final else None,
            }
        )
    return pd.DataFrame(rows)


st.title("UPI Payment Failure Recovery Agent")
st.caption("Track 3 submission for the Razorpay AI Buildathon 2026")

if "cache_bust" not in st.session_state:
    st.session_state.cache_bust = 0

if st.button("Run Batch (200 transactions)"):
    with st.spinner("Running full recovery pipeline..."):
        asyncio.run(run_recovery_batch())
    st.session_state.cache_bust += 1
    st.success("Batch complete.")

transactions, by_txn = _load_data(st.session_state.cache_bust)

if not by_txn:
    st.warning("No audit log found yet. Click 'Run Batch' above to generate one.")
    st.stop()

tab_metrics, tab_transactions, tab_drilldown, tab_random = st.tabs(
    ["Metrics", "Transactions Table", "Drilldown", "Random Failures"]
)

with tab_metrics:
    metrics = compute_metrics()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Overall recovery rate", f"{metrics['overall_recovery_rate']:.1%}")
    col2.metric("Classification macro-F1", f"{metrics['macro_f1']:.3f}")
    col3.metric("Cost per recovery", f"${metrics['cost_per_recovery_usd']:.5f}")
    col4.metric("Groq fallback rate", f"{metrics['fallback_rate']:.1%}")

    st.subheader("Recovery rate by predicted root cause")
    st.dataframe(
        pd.DataFrame(
            [{"root_cause": k, "recovery_rate": v} for k, v in metrics["per_bucket_recovery_rate"].items()]
        ),
        hide_index=True,
    )

    st.subheader("Tier routing distribution")
    st.dataframe(
        pd.DataFrame(
            [{"tier": k, "share_of_traffic": v} for k, v in metrics["tier_distribution"].items()]
        ),
        hide_index=True,
    )

    st.subheader("Stopping rule breakdown (abandoned transactions)")
    st.dataframe(
        pd.DataFrame(
            [{"reason": k, "count": v} for k, v in metrics["stopping_rule_counts"].items()]
        ),
        hide_index=True,
    )

    st.subheader("Confusion matrix (true -> predicted)")
    st.dataframe(
        pd.DataFrame(
            [{"pair": k, "count": v} for k, v in metrics["confusion_matrix"].items()]
        ),
        hide_index=True,
    )

with tab_transactions:
    df = _build_transactions_table(transactions, by_txn)
    st.dataframe(df, hide_index=True, width="stretch")

with tab_drilldown:
    txn_ids = sorted(transactions.keys())
    selected = st.selectbox("Transaction ID", txn_ids)
    if selected:
        st.write(transactions[selected].model_dump())
        st.subheader("Full audit trail")
        for entry in by_txn.get(selected, []):
            with st.expander(f"{entry.stage} @ {entry.timestamp}"):
                st.json(entry.model_dump(mode="json"))

with tab_random:
    st.write("5 random abandoned transactions, picked live, not cherry-picked.")
    if st.button("Show me 5 random failures"):
        abandoned_ids = [
            txn_id for txn_id, entries in by_txn.items() if entries and entries[-1].stage == "abandoned"
        ]
        sample = random.sample(abandoned_ids, min(5, len(abandoned_ids)))
        for txn_id in sample:
            st.subheader(f"TXN {txn_id}")
            st.write(transactions[txn_id].model_dump())
            for entry in by_txn[txn_id]:
                with st.expander(f"{entry.stage} @ {entry.timestamp}"):
                    st.json(entry.model_dump(mode="json"))
