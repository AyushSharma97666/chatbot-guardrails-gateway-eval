"""
Evaluation & Safety Dashboard.

Reads exclusively from database/system.db through utils/audit_log.py,
utils/query_cache.py, and evaluation/run_eval.py's read helpers — no raw
SQL inline in this file. "Run Evaluation Now" calls
evaluation.run_eval.run_full_suite(), which routes every case through
utils.chat_gateway.ask_question() — the same single chokepoint the real
chat UI uses.
"""

import os
import sys

import pandas as pd
import streamlit as st
import plotly.express as px

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import config
from utils.logger import get_logger
from utils import audit_log, query_cache
from evaluation import run_eval

logger = get_logger("eval_page")

st.set_page_config(
    page_title="Evaluation - Healthcare Analytics",
    page_icon="hospital",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp { background: #f8f9fb; }
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }

    .dashboard-header {
        background: linear-gradient(135deg, #1a365d 0%, #2c5282 100%);
        color: white; padding: 1.2rem 1.8rem; border-radius: 10px;
        margin-bottom: 1.2rem; box-shadow: 0 2px 8px rgba(0,0,0,0.12);
    }
    .dashboard-header h1 { color: white; margin: 0; font-size: 1.6rem; font-weight: 700; }
    .dashboard-header p  { color: #bee3f8; margin: 0.3rem 0 0 0; font-size: 0.88rem; }

    .kpi-card {
        background: white; border-radius: 10px; padding: 1rem 1.2rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08); text-align: center;
        border-top: 3px solid #3182ce; height: 100%; transition: transform 0.15s;
    }
    .kpi-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.12); }
    .kpi-value { font-size: 1.8rem; font-weight: 700; color: #1a365d; line-height: 1.2; }
    .kpi-label { font-size: 0.78rem; color: #718096; margin-top: 0.2rem; text-transform: uppercase; letter-spacing: 0.04em; }
    .kpi-card.red   { border-top-color: #e53e3e; }
    .kpi-card.green { border-top-color: #38a169; }
    .kpi-card.orange{ border-top-color: #dd6b20; }
    .kpi-card.purple{ border-top-color: #805ad5; }
    .kpi-card.teal  { border-top-color: #319795; }

    .section-header {
        background: white; border-left: 4px solid #3182ce; padding: 0.6rem 1rem;
        border-radius: 0 6px 6px 0; margin: 1.2rem 0 0.8rem 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .section-header h2 { margin: 0; font-size: 1.05rem; color: #1a365d; }
    .section-header p  { margin: 0.15rem 0 0 0; font-size: 0.78rem; color: #718096; }

    .chart-box {
        background: white; border-radius: 10px; padding: 1rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06); height: 100%;
    }

    section[data-testid="stSidebar"] { background: #1a365d; }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 { color: white; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## Evaluation & Safety")
    st.markdown("---")
    st.markdown(
        "Correctness (golden set) and safety (adversarial set) regression "
        "checks for the chatbot's guardrails. Every case runs through the "
        "same gateway real chat traffic uses."
    )

st.markdown("""
<div class="dashboard-header">
    <h1>Evaluation & Safety Dashboard</h1>
    <p>Correctness, safety, cache, and cost — measured against the live chatbot gateway</p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# RUN EVALUATION
# ─────────────────────────────────────────────────────────────
run_col, note_col = st.columns([1, 3])
with run_col:
    run_clicked = st.button("Run Evaluation Now", type="primary", use_container_width=True)
with note_col:
    st.caption(
        "Non-destructive — issues read-only SELECTs and appends rows to the eval log. "
        "Calls the live Gemini API once per case (~30+ calls), so it takes a minute or two."
    )

if run_clicked:
    with st.spinner("Running golden + adversarial suites against the live gateway..."):
        summary = run_eval.run_full_suite(triggered_by="manual_button")
    st.success(
        f"Run {summary['run_id']} complete — "
        f"golden {summary['golden_pass_rate']:.0%}, adversarial {summary['adversarial_pass_rate']:.0%}"
    )
    st.rerun()


# ─────────────────────────────────────────────────────────────
# STAT TILES
# ─────────────────────────────────────────────────────────────
latest_golden = run_eval.get_latest_run("golden")
latest_adversarial = run_eval.get_latest_run("adversarial")
cache_hit_rate = audit_log.compute_cache_hit_rate()
latency_df = audit_log.compute_latency_trend()
avg_latency = latency_df["avg_latency_ms"].mean() if not latency_df.empty else None

golden_rate = latest_golden["pass_rate"] if latest_golden else None
adversarial_rate = latest_adversarial["pass_rate"] if latest_adversarial else None

kpi_html = f"""
<div style="display:grid; grid-template-columns:repeat(4,1fr); gap:0.8rem; margin-bottom:1rem;">
    <div class="kpi-card {'green' if (golden_rate or 0) >= 0.8 else 'orange' if golden_rate is not None else ''}">
        <div class="kpi-value">{f'{golden_rate:.0%}' if golden_rate is not None else '—'}</div>
        <div class="kpi-label">Correctness (Golden Set)</div>
    </div>
    <div class="kpi-card {'green' if (adversarial_rate or 0) >= 0.95 else 'red' if adversarial_rate is not None else ''}">
        <div class="kpi-value">{f'{adversarial_rate:.0%}' if adversarial_rate is not None else '—'}</div>
        <div class="kpi-label">Safety Score (Adversarial Set)</div>
    </div>
    <div class="kpi-card teal">
        <div class="kpi-value">{cache_hit_rate:.0%}</div>
        <div class="kpi-label">Cache Hit Rate</div>
    </div>
    <div class="kpi-card purple">
        <div class="kpi-value">{f'{avg_latency:,.0f}ms' if avg_latency is not None else '—'}</div>
        <div class="kpi-label">Avg Latency</div>
    </div>
</div>
"""
st.markdown(kpi_html, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# LATEST RUN RESULTS
# ─────────────────────────────────────────────────────────────
results_col1, results_col2 = st.columns(2)

_DISPLAY_COLS = ["case_id", "question", "actual_outcome", "passed", "detail", "latency_ms"]

with results_col1:
    st.markdown("""
    <div class="section-header">
        <h2>Correctness — Latest Golden Run</h2>
        <p>Does the generated SQL still answer known questions correctly?</p>
    </div>
    """, unsafe_allow_html=True)

    if latest_golden:
        cases_df = run_eval.get_case_results(latest_golden["run_id"], "golden")
        st.dataframe(cases_df[_DISPLAY_COLS], use_container_width=True, hide_index=True)
    else:
        st.info("No golden-set run yet. Click \"Run Evaluation Now\" above.")

with results_col2:
    st.markdown("""
    <div class="section-header">
        <h2>Safety — Latest Adversarial Run</h2>
        <p>Are injection/DML/PII-fishing attempts still being blocked or redacted?</p>
    </div>
    """, unsafe_allow_html=True)

    if latest_adversarial:
        cases_df = run_eval.get_case_results(latest_adversarial["run_id"], "adversarial")
        st.dataframe(cases_df[_DISPLAY_COLS], use_container_width=True, hide_index=True)
    else:
        st.info("No adversarial-set run yet. Click \"Run Evaluation Now\" above.")


# ─────────────────────────────────────────────────────────────
# TRENDS OVER TIME
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="section-header">
    <h2>Trends Over Time</h2>
    <p>Pass rates, latency, and estimated cost across evaluation runs and chat traffic</p>
</div>
""", unsafe_allow_html=True)

trend_col1, trend_col2 = st.columns(2)

with trend_col1:
    golden_history = run_eval.get_run_history("golden")
    adversarial_history = run_eval.get_run_history("adversarial")

    if not golden_history.empty or not adversarial_history.empty:
        golden_history = golden_history.assign(suite="golden") if not golden_history.empty else golden_history
        adversarial_history = adversarial_history.assign(suite="adversarial") if not adversarial_history.empty else adversarial_history
        combined = pd.concat([golden_history, adversarial_history], ignore_index=True)
        fig = px.line(
            combined, x="finished_at", y="pass_rate", color="suite", markers=True,
            title="Pass Rate by Run", color_discrete_map={"golden": "#3182ce", "adversarial": "#e53e3e"},
        )
        fig.update_layout(yaxis_tickformat=".0%", height=350)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No evaluation history yet.")

with trend_col2:
    cost_df = audit_log.compute_token_cost_trend()
    if not cost_df.empty:
        fig = px.bar(cost_df, x="bucket", y="estimated_cost_usd", title="Estimated Cost per Day (USD)")
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No token/cost data yet — ask the chatbot a few questions first.")


# ─────────────────────────────────────────────────────────────
# CACHE PERFORMANCE
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="section-header">
    <h2>Cache Performance</h2>
    <p>Exact-match question cache — repeat questions skip SQL generation entirely</p>
</div>
""", unsafe_allow_html=True)

cache_stats = query_cache.get_cache_stats()
cache_col1, cache_col2 = st.columns([1, 2])

with cache_col1:
    st.metric("Cached Questions", f"{cache_stats['total_entries']:,}")
    st.metric("Total Cache Hits", f"{cache_stats['total_hits']:,}")

with cache_col2:
    if cache_stats["top_questions"]:
        st.dataframe(pd.DataFrame(cache_stats["top_questions"]), use_container_width=True, hide_index=True)
    else:
        st.info("No cached questions yet.")
