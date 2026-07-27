"""
Healthcare Analytics Dashboard
Professional stakeholder-facing dashboard with curated visualizations and AI chatbot.
"""

import os
import sys
import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import config
from utils.logger import get_logger
from utils.chat_gateway import ask_question

logger = get_logger("app")

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Healthcare Analytics",
    page_icon="hospital",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATABASE_PATH = config.DATABASE_PATH

# ─────────────────────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Global */
    .stApp { background: #f564c5; } 
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }

    /* Header */
    .dashboard-header {
        background: linear-gradient(135deg, #1a365d 0%, #2c5282 100%);
        color: white; padding: 1.2rem 1.8rem; border-radius: 10px;
        margin-bottom: 1.2rem; box-shadow: 0 2px 8px rgba(0,0,0,0.12);
    }
    .dashboard-header h1 { color: white; margin: 0; font-size: 1.6rem; font-weight: 700; }
    .dashboard-header p  { color: #bee3f8; margin: 0.3rem 0 0 0; font-size: 0.88rem; }

    /* KPI cards */
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

    /* Section headers */
    .section-header {
        background: white; border-left: 4px solid #3182ce; padding: 0.6rem 1rem;
        border-radius: 0 6px 6px 0; margin: 1.2rem 0 0.8rem 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .section-header h2 { margin: 0; font-size: 1.05rem; color: #1a365d; }
    .section-header p  { margin: 0.15rem 0 0 0; font-size: 0.78rem; color: #718096; }

    /* Chart containers */
    .chart-box {
        background: white; border-radius: 10px; padding: 1rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06); height: 100%;
    }

    /* Chatbot section */
    .chatbot-header {
        background: linear-gradient(135deg, #2d3748 0%, #4a5568 100%);
        color: white; padding: 0.8rem 1.4rem; border-radius: 10px;
        margin: 1.5rem 0 0.8rem 0; display: flex; align-items: center; gap: 0.6rem;
    }
    .chatbot-header h2 { color: white; margin: 0; font-size: 1.1rem; }

    /* Sidebar */
    section[data-testid="stSidebar"] { background: #1a365d; }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 { color: white; }

    /* Chat messages - force readable text regardless of the browser/OS
       theme Streamlit negotiates, since .stApp's forced light background
       above can otherwise end up paired with light theme text (near-
       invisible until selected). */
    div[data-testid="stChatMessage"] {
        background: #ffffff !important;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    div[data-testid="stChatMessageContent"],
    div[data-testid="stChatMessageContent"] p,
    div[data-testid="stChatMessageContent"] li,
    div[data-testid="stChatMessageContent"] span,
    div[data-testid="stChatMessageContent"] div {
        color: #1a202c !important;
    }

    /* Ensure Plotly chart labels are visible */
    .stPlotlyChart { overflow: visible !important; }
    .js-plotly-plot .plotly .main-svg { overflow: visible !important; }

    /* Make bar text labels more prominent */
    .gtitle, .xtitle, .ytitle { font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# DATA LAYER
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def query_db(sql: str) -> pd.DataFrame:
    conn = sqlite3.connect(DATABASE_PATH)
    df = pd.read_sql_query(sql, conn)
    conn.close()
    return df


@st.cache_data(ttl=300)
def load_all_data():
    tables = {}
    conn = sqlite3.connect(DATABASE_PATH)
    for name in ["Patients", "Encounters", "Accounts", "SurgicalEncounters",
                  "SurgicalCosts", "QualityMeasureData", "Hospitals",
                  "Departments", "OrdersProcedures", "Results", "Physicians"]:
        tables[name] = pd.read_sql_query(f"SELECT * FROM [{name}]", conn)
    conn.close()

    p = tables["Patients"]
    e = tables["Encounters"]
    s = tables["SurgicalEncounters"]
    q = tables["QualityMeasureData"]
    a = tables["Accounts"]
    h = tables["Hospitals"]
    d = tables["Departments"]
    v = tables.get("Vitals", pd.DataFrame())

    # Date parsing
    p["Patient DOB"] = pd.to_datetime(p["Patient DOB"], errors="coerce")
    p["Age"] = ((pd.Timestamp("2016-01-01") - p["Patient DOB"]).dt.days / 365.25).round(0)
    e["Admission Dt"] = pd.to_datetime(e["Patient Admission Datetime"], errors="coerce")
    e["Readmit"] = e["Patient Readmission Flag"].map({"Yes": 1, "No": 0})
    e["ICU"] = e["Patient InICU Flag"].map({"Yes": 1, "No": 0})
    s["Admission Dt"] = pd.to_datetime(s["Surgical Admission Date"], errors="coerce")
    s["Profit Margin %"] = (s["Surgical Total Profit"] / s["Surgical Total Cost"] * 100).round(1)
    q["Compliant"] = q["IsCompliant"].map({"Yes": 1, "No": 0})
    q["Effective Dt"] = pd.to_datetime(q["Measure Effective Date"], errors="coerce")

    # Hospital linkage for encounters
    dept_hosp = d[["Department ID", "Hospital ID"]].drop_duplicates()
    hosp_lookup = h[["Hospital ID", "Hospital Name", "Hospital City"]].drop_duplicates()
    e_h = e.merge(dept_hosp, on="Department ID", how="left").merge(hosp_lookup, on="Hospital ID", how="left")

    return {
        "patients": p, "encounters": e, "accounts": a, "surg_enc": s,
        "surg_costs": tables["SurgicalCosts"], "quality": q,
        "hospitals": h, "departments": d, "enc_h": e_h, "vitals": v,
    }


data = load_all_data()
patients    = data["patients"]
encounters  = data["encounters"]
accounts    = data["accounts"]
surg_enc    = data["surg_enc"]
surg_costs  = data["surg_costs"]
quality     = data["quality"]
hospitals   = data["hospitals"]
departments = data["departments"]
enc_h       = data["enc_h"]


# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Healthcare Analytics")
    st.markdown("---")
    st.markdown("### Database Info")
    if os.path.exists(DATABASE_PATH):
        db_mtime = datetime.fromtimestamp(os.path.getmtime(DATABASE_PATH))
        st.caption(f"Last updated: {db_mtime.strftime('%Y-%m-%d %H:%M')}")
    st.caption(f"Tables: 13 | Patients: {len(patients):,} | Records: ~1,100")

    st.markdown("---")
    st.markdown("### Quick Stats")
    st.metric("Encounters", f"{len(encounters):,}")
    st.metric("Surgeries", f"{len(surg_enc):,}")
    st.metric("Quality Records", f"{len(quality):,}")

    st.markdown("---")
    st.markdown("### Navigation")
    st.markdown("""
    1. **KPI Overview** — Top-line metrics
    2. **Readmission Risk** — Hospital comparison
    3. **Surgical Profitability** — DRG analysis
    4. **Quality Compliance** — Measure tracking
    5. **AI Chatbot** — Ask anything
    """)

    st.markdown("---")
    st.caption("Built with Streamlit + Plotly")


# ─────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="dashboard-header">
    <h1>Healthcare Analytics Dashboard</h1>
    <p>Clinical Operations &amp; Financial Performance Overview | Data Period: 2015-2016</p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# KPI BANNER
# ─────────────────────────────────────────────────────────────
total_patients   = len(patients)
total_encounters = len(encounters)
readmit_rate     = encounters["Readmit"].mean() * 100
icu_rate         = encounters["ICU"].mean() * 100
avg_los          = encounters["Patient LOS"].mean()
quality_rate     = quality["Compliant"].mean() * 100

kpi_html = f"""
<div style="display:grid; grid-template-columns:repeat(6,1fr); gap:0.8rem; margin-bottom:1rem;">
    <div class="kpi-card">
        <div class="kpi-value">{total_patients:,}</div>
        <div class="kpi-label">Total Patients</div>
    </div>
    <div class="kpi-card green">
        <div class="kpi-value">{total_encounters:,}</div>
        <div class="kpi-label">Total Encounters</div>
    </div>
    <div class="kpi-card red">
        <div class="kpi-value">{readmit_rate:.0f}%</div>
        <div class="kpi-label">Readmission Rate</div>
    </div>
    <div class="kpi-card orange">
        <div class="kpi-value">{icu_rate:.0f}%</div>
        <div class="kpi-label">ICU Rate</div>
    </div>
    <div class="kpi-card purple">
        <div class="kpi-value">{avg_los:.1f}d</div>
        <div class="kpi-label">Avg Length of Stay</div>
    </div>
    <div class="kpi-card teal">
        <div class="kpi-value">{quality_rate:.0f}%</div>
        <div class="kpi-label">Quality Compliance</div>
    </div>
</div>
"""
st.markdown(kpi_html, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# SECTION 1: READMISSION RISK BY HOSPITAL
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="section-header">
    <h2>Readmission Risk by Hospital</h2>
    <p>30-day readmission rate per facility — CMS penalizes hospitals exceeding national benchmarks</p>
</div>
""", unsafe_allow_html=True)

hosp_readmit = enc_h.groupby("Hospital Name").agg(
    Readmit_Rate=("Readmit", "mean"),
    Count=("Patient Encounter ID", "count"),
    ICU_Rate=("ICU", "mean"),
).sort_values("Readmit_Rate", ascending=True).reset_index()
hosp_readmit["Readmit_Pct"] = hosp_readmit["Readmit_Rate"] * 100
hosp_readmit["Color"] = hosp_readmit["Readmit_Pct"].apply(
    lambda x: "#38a169" if x < 25 else "#dd6b20" if x < 50 else "#e53e3e"
)

fig_readmit = go.Figure()
fig_readmit.add_trace(go.Bar(
    y=hosp_readmit["Hospital Name"],
    x=hosp_readmit["Readmit_Pct"],
    orientation="h",
    marker_color=hosp_readmit["Color"],
    text=[f"{r:.0f}% (n={int(c)})" for r, c in zip(hosp_readmit["Readmit_Pct"], hosp_readmit["Count"])],
    textposition="outside",
    textfont=dict(size=13, color="#1a365d"),
    hovertemplate="<b>%{y}</b><br>Readmit: %{x:.1f}%<br>Cases: %{customdata}<extra></extra>",
    customdata=hosp_readmit["Count"],
))
overall_readmit = encounters["Readmit"].mean() * 100
fig_readmit.add_vline(x=overall_readmit, line_dash="dash", line_color="red", line_width=1.5,
                       annotation_text=f"Network Avg: {overall_readmit:.0f}%",
                       annotation_position="top right", annotation_font_color="red",
                       annotation_font_size=12)
fig_readmit.update_layout(
    height=320, margin=dict(l=180, r=60, t=15, b=45),
    xaxis_title="Readmission Rate (%)",
    xaxis=dict(range=[0, 105], title=dict(font=dict(size=13)), tickfont=dict(size=12)),
    yaxis=dict(categoryorder="total ascending", tickfont=dict(size=13, color="#1a365d")),
    plot_bgcolor="white", paper_bgcolor="white",
    font=dict(size=12, color="#2d3748"),
)
with st.container():
    c1, c2 = st.columns([3, 1])
    with c1:
        st.plotly_chart(fig_readmit, use_container_width=True)
    with c2:
        st.markdown("""
        **Key Insights:**
        - Higher readmission rates signal gaps in discharge planning
        - CMS HRRP program penalizes excess readmissions
        - Target: **<15%** for optimal performance
        - Investigate top performer for best practices
        """)


# ─────────────────────────────────────────────────────────────
# SECTION 2: SURGICAL DRG PROFITABILITY
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="section-header">
    <h2>Surgical DRG Profitability</h2>
    <p>Average profit or loss per surgical case by Diagnosis Related Group</p>
</div>
""", unsafe_allow_html=True)

drg_profit = surg_enc.groupby("Surgical DRG Description").agg(
    Avg_Profit=("Surgical Total Profit", "mean"),
    Cases=("Surgery ID", "count"),
    Avg_Cost=("Surgical Total Cost", "mean"),
    Avg_LOS=("Surgical LOS", "mean"),
).sort_values("Avg_Profit", ascending=True).reset_index()
drg_profit["Color"] = drg_profit["Avg_Profit"].apply(lambda x: "#38a169" if x >= 0 else "#e53e3e")
drg_profit["Label"] = drg_profit.apply(
    lambda r: f"${r['Avg_Profit']:,.0f} (n={r['Cases']})", axis=1
)

fig_profit = go.Figure()
fig_profit.add_trace(go.Bar(
    y=drg_profit["Surgical DRG Description"],
    x=drg_profit["Avg_Profit"],
    orientation="h",
    marker_color=drg_profit["Color"],
    text=drg_profit["Label"],
    textposition="outside",
    textfont=dict(size=12, color="#1a365d"),
    hovertemplate="<b>%{y}</b><br>Avg Profit: $%{x:,.0f}<br>Cases: %{customdata[0]}<br>Avg Cost: $%{customdata[1]:,.0f}<br>Avg LOS: %{customdata[2]:.1f}d<extra></extra>",
    customdata=drg_profit[["Cases", "Avg_Cost", "Avg_LOS"]].values,
))
fig_profit.add_vline(x=0, line_color="black", line_width=1)
fig_profit.update_layout(
    height=420, margin=dict(l=250, r=80, t=15, b=45),
    xaxis_title="Average Profit per Case ($)",
    xaxis=dict(title=dict(font=dict(size=13)), tickfont=dict(size=12), tickprefix="$"),
    yaxis=dict(categoryorder="total ascending", tickfont=dict(size=12, color="#1a365d")),
    plot_bgcolor="white", paper_bgcolor="white",
    font=dict(size=12, color="#2d3748"),
)
with st.container():
    c1, c2 = st.columns([3, 1])
    with c1:
        st.plotly_chart(fig_profit, use_container_width=True)
    with c2:
        profitable = (drg_profit["Avg_Profit"] >= 0).sum()
        total_drgs = len(drg_profit)
        st.markdown(f"""
        **Key Insights:**
        - **{profitable}/{total_drgs}** DRGs are profitable
        - Caesarean Sections generate the **largest losses**
        - Normal/Assisted Deliveries are **most profitable**
        - Review C-section cost structure for savings
        - Target: Positive margin on all elective procedures
        """)
        st.metric("Profitable DRGs", f"{profitable}/{total_drgs}")


# ─────────────────────────────────────────────────────────────
# SECTION 3: QUALITY MEASURE COMPLIANCE
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="section-header">
    <h2>Quality Measure Compliance</h2>
    <p>Clinical quality measure compliance rates — impacts CMS Star Ratings and reimbursement</p>
</div>
""", unsafe_allow_html=True)

measure_comp = quality.groupby("Measure Name").agg(
    Rate=("Compliant", "mean"),
    Count=("Compliant", "count"),
    Compliant=("Compliant", "sum"),
).sort_values("Rate", ascending=True).reset_index()
measure_comp["Pct"] = measure_comp["Rate"] * 100
measure_comp["Color"] = measure_comp["Pct"].apply(
    lambda x: "#38a169" if x >= 75 else "#dd6b20" if x >= 50 else "#e53e3e"
)
measure_comp["Label"] = measure_comp.apply(
    lambda r: f"{r['Pct']:.0f}% ({int(r['Compliant'])}/{int(r['Count'])})", axis=1
)

fig_quality = go.Figure()
fig_quality.add_trace(go.Bar(
    y=measure_comp["Measure Name"],
    x=measure_comp["Pct"],
    orientation="h",
    marker_color=measure_comp["Color"],
    text=measure_comp["Label"],
    textposition="outside",
    textfont=dict(size=13, color="#1a365d"),
    hovertemplate="<b>%{y}</b><br>Compliance: %{x:.1f}%<br>Cases: %{customdata}<extra></extra>",
    customdata=measure_comp["Count"],
))
fig_quality.add_vline(x=50, line_dash="dash", line_color="red", line_width=1,
                       annotation_text="50% threshold", annotation_position="bottom right",
                       annotation_font_color="red", annotation_font_size=11)
fig_quality.add_vline(x=75, line_dash="dash", line_color="green", line_width=1,
                       annotation_text="75% CMS target", annotation_position="top right",
                       annotation_font_color="green", annotation_font_size=11)
fig_quality.update_layout(
    height=380, margin=dict(l=220, r=70, t=15, b=45),
    xaxis_title="Compliance Rate (%)",
    xaxis=dict(range=[0, 115], title=dict(font=dict(size=13)), tickfont=dict(size=12)),
    yaxis=dict(categoryorder="total ascending", tickfont=dict(size=12, color="#1a365d")),
    plot_bgcolor="white", paper_bgcolor="white",
    font=dict(size=12, color="#2d3748"),
)
with st.container():
    c1, c2 = st.columns([3, 1])
    with c1:
        st.plotly_chart(fig_quality, use_container_width=True)
    with c2:
        above_75 = (measure_comp["Pct"] >= 75).sum()
        below_50 = (measure_comp["Pct"] < 50).sum()
        st.markdown(f"""
        **Key Insights:**
        - **{below_50}/{len(measure_comp)}** measures below 50% — critical gap
        - Only **{above_75}** measures meet the 75% CMS target
        - Pneumococcal Vaccine is the **top performer**
        - Cancer screening measures need immediate attention
        - Action: Automate patient outreach for screenings
        """)
        st.metric("Measures at Target", f"{above_75}/{len(measure_comp)}")


# ─────────────────────────────────────────────────────────────
# SECTION 4: HOSPITAL PERFORMANCE BENCHMARKING
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="section-header">
    <h2>Hospital Performance Benchmarking</h2>
    <p>Side-by-side comparison across clinical and operational dimensions</p>
</div>
""", unsafe_allow_html=True)

hosp_bench = enc_h.groupby("Hospital Name").agg(
    Readmit=("Readmit", "mean"),
    ICU=("ICU", "mean"),
    LOS=("Patient LOS", "mean"),
    Count=("Readmit", "count"),
).sort_values("Count", ascending=False).reset_index()

fig_bench = go.Figure()
fig_bench.add_trace(go.Bar(
    name="Readmit %", x=hosp_bench["Hospital Name"], y=hosp_bench["Readmit"] * 100,
    marker_color="#e53e3e", text=[f"{r*100:.0f}%" for r in hosp_bench["Readmit"]],
    textposition="outside", textfont=dict(size=11, color="#1a365d"),
))
fig_bench.add_trace(go.Bar(
    name="ICU %", x=hosp_bench["Hospital Name"], y=hosp_bench["ICU"] * 100,
    marker_color="#dd6b20", text=[f"{r*100:.0f}%" for r in hosp_bench["ICU"]],
    textposition="outside", textfont=dict(size=11, color="#1a365d"),
))
fig_bench.add_trace(go.Bar(
    name="Avg LOS", x=hosp_bench["Hospital Name"], y=hosp_bench["LOS"],
    marker_color="#3182ce", text=[f"{r:.1f}d" for r in hosp_bench["LOS"]],
    textposition="outside", textfont=dict(size=11, color="#1a365d"),
))
fig_bench.update_layout(
    barmode="group", height=380, margin=dict(l=10, r=10, t=30, b=80),
    yaxis_title="Rate (%) / Days",
    yaxis=dict(title=dict(font=dict(size=13)), tickfont=dict(size=12)),
    xaxis=dict(tickfont=dict(size=12, color="#1a365d"), tickangle=-20),
    plot_bgcolor="white", paper_bgcolor="white",
    legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="center", x=0.5,
                font=dict(size=12)),
    font=dict(size=12, color="#2d3748"),
)
with st.container():
    c1, c2 = st.columns([3, 1])
    with c1:
        st.plotly_chart(fig_bench, use_container_width=True)
    with c2:
        best_h = hosp_bench.loc[hosp_bench["Readmit"].idxmin(), "Hospital Name"]
        worst_h = hosp_bench.loc[hosp_bench["Readmit"].idxmax(), "Hospital Name"]
        st.markdown(f"""
        **Key Insights:**
        - **Best performer:** {best_h}
        - **Needs improvement:** {worst_h}
        - ICU rate variation suggests triage protocol differences
        - LOS variation indicates throughput efficiency gaps
        - Action: Share best practices across network
        """)
        st.metric("Best Performer", best_h)


# ─────────────────────────────────────────────────────────────
# AI CHATBOT
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="chatbot-header">
    <h2>AI Data Chatbot</h2>
</div>
""", unsafe_allow_html=True)
st.markdown("Ask questions about your healthcare data in natural language. The AI will query the database and return results.")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "data_preview" in msg:
            with st.expander("View Query Results"):
                st.dataframe(msg["data_preview"], use_container_width=True, hide_index=True)

user_input = st.chat_input("Ask a question about your healthcare data...")

if user_input:
    logger.info(f"User question: {user_input}")
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Querying database..."):
            try:
                result = ask_question(user_input)

                if result["blocked"] or not result["success"]:
                    reply = result["narration"]
                    st.markdown(reply)
                    st.session_state.chat_history.append({"role": "assistant", "content": reply})
                else:
                    df = result["df"]

                    with st.expander("SQL Query Used"):
                        st.code(result["sql"], language="sql")
                        if result["cache_hit"]:
                            st.caption("Answered from cache — re-run fresh against the live database.")

                    st.dataframe(df, use_container_width=True, hide_index=True)
                    if result["masked_columns"]:
                        st.caption(f"{len(result['masked_columns'])} column(s) hidden for privacy.")

                    reply = result["narration"]
                    st.markdown(reply)
                    st.session_state.chat_history.append({
                        "role": "assistant", "content": reply, "data_preview": df,
                    })

            except Exception as e:
                logger.error(f"Chatbot error: {e}", exc_info=True)
                reply = f"An error occurred: {str(e)}"
                st.markdown(reply)
                st.session_state.chat_history.append({"role": "assistant", "content": reply})


# ─────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align:center; color:#a0aec0; font-size:0.75rem; padding:0.5rem 0;'>"
    "Healthcare Analytics Dashboard | Data Period: 2015-2016 | "
    f"Generated: {datetime.now().strftime('%B %d, %Y')}"
    "</div>",
    unsafe_allow_html=True,
)
