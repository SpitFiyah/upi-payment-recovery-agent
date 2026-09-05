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

import os

DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1" or not os.getenv("GEMINI_API_KEY") or not os.getenv("GROQ_API_KEY")

st.set_page_config(
    page_title="UPI Payment Failure Recovery Agent",
    page_icon="UPI",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    .stApp {
        background: radial-gradient(circle at top left, rgba(16, 185, 129, 0.16), transparent 28%),
                    radial-gradient(circle at top right, rgba(59, 130, 246, 0.14), transparent 24%),
                    linear-gradient(180deg, #f8fbff 0%, #eef5ff 100%);
    }
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2.4rem;
        max-width: 1280px;
    }
    .hero-wrap {
        padding: 1.4rem 1.5rem 1.2rem 1.5rem;
        border: 1px solid rgba(15, 23, 42, 0.08);
        border-radius: 24px;
        background: rgba(255, 255, 255, 0.82);
        box-shadow: 0 18px 60px rgba(15, 23, 42, 0.09);
        backdrop-filter: blur(10px);
        margin-bottom: 1rem;
    }
    .eyebrow {
        display: inline-block;
        padding: 0.35rem 0.7rem;
        border-radius: 999px;
        background: linear-gradient(90deg, #0f766e, #1d4ed8);
        color: white;
        font-size: 0.76rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.75rem;
    }
    .hero-title {
        font-size: 2.35rem;
        line-height: 1.05;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 0.45rem;
    }
    .hero-subtitle {
        font-size: 1.02rem;
        line-height: 1.5;
        color: #334155;
        max-width: 920px;
        margin-bottom: 0.85rem;
    }
    .pill-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-bottom: 0.25rem;
    }
    .pill {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.36rem 0.7rem;
        border-radius: 999px;
        background: #eef2ff;
        color: #1e3a8a;
        font-size: 0.82rem;
        font-weight: 600;
        border: 1px solid rgba(37, 99, 235, 0.12);
    }
    .metric-card {
        padding: 0.95rem 1rem;
        border-radius: 18px;
        background: white;
        border: 1px solid rgba(15, 23, 42, 0.08);
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.06);
        min-height: 102px;
    }
    .metric-label {
        color: #64748b;
        font-size: 0.82rem;
        font-weight: 600;
        letter-spacing: 0.01em;
        margin-bottom: 0.35rem;
    }
    .metric-value {
        color: #0f172a;
        font-size: 1.65rem;
        font-weight: 800;
        line-height: 1;
        margin-bottom: 0.25rem;
    }
    .metric-note {
        color: #475569;
        font-size: 0.82rem;
    }
    div[data-testid="stTab"] {
        font-weight: 700;
    }
    .stButton > button {
        border-radius: 14px;
        border: 0;
        background: linear-gradient(90deg, #0f766e, #1d4ed8);
        color: white;
        font-weight: 700;
        padding: 0.75rem 1.1rem;
        box-shadow: 0 12px 30px rgba(29, 78, 216, 0.22);
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 16px 34px rgba(29, 78, 216, 0.26);
    }
</style>
""",
    unsafe_allow_html=True,
)


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

if DEMO_MODE:
    st.warning("Demo mode is active. The app will use mock fallback classification if Gemini or Groq keys are missing.")

hero_col1, hero_col2 = st.columns([4, 1])
with hero_col1:
    st.markdown(
        """
        <div class="hero-wrap">
            <div class="eyebrow">Demo ready</div>
            <div class="hero-title">UPI payment recovery with measured batch results.</div>
            <div class="hero-subtitle">
                This app classifies failed UPI transactions through a deterministic-first cascade,
                applies bounded retry logic, and writes an audit trail you can show live in a screen recording.
            </div>
            <div class="pill-row">
                <span class="pill">Keyword first</span>
                <span class="pill">Local embedding</span>
                <span class="pill">Gemini fallback</span>
                <span class="pill">Groq backup</span>
                <span class="pill">Audit trail</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with hero_col2:
    st.markdown(
        """
        <div class="metric-card">
            <div class="metric-label">Recording mode</div>
            <div class="metric-value">Live</div>
            <div class="metric-note">Open the app, click Run Batch, then record the tabs below.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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

    metric_cols = st.columns(4)
    metric_data = [
        ("Overall recovery rate", f"{metrics['overall_recovery_rate']:.1%}", "Recovered from the batch"),
        ("Classification macro-F1", f"{metrics['macro_f1']:.3f}", "Ground-truth comparison"),
        ("Cost per recovery", f"${metrics['cost_per_recovery_usd']:.5f}", "LLM cost normalized"),
        ("Groq fallback rate", f"{metrics['fallback_rate']:.1%}", "Provider fallback share"),
    ]
    for col, (label, value, note) in zip(metric_cols, metric_data):
        with col:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value">{value}</div>
                    <div class="metric-note">{note}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.write("")
    st.info("Use the Drilldown tab to show one transaction trace, then switch to Random Failures for the anti-cherry-pick shot.")

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
