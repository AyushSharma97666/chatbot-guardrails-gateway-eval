# Healthcare Analytics Dashboard — Visual Guide

> **Audience:** Clinical Operations, Hospital Administration, Finance Teams
> **Last Updated:** July 2026
> **Database:** HealthcareDB.db (13 tables, 100+ records each)

---

## Dashboard Overview

The dashboard is organized into **3 sections**:

| Section | Purpose |
|---------|---------|
| KPI Banner | At-a-glance summary of core operational metrics |
| Analytics Panels (2x2 grid) | Deep-dive into the 4 most critical decision areas |
| AI Chatbot | Natural language interface for ad-hoc data queries |

---

## KPI Banner — Key Performance Indicators

Six headline metrics displayed at the top of every page:

| Metric | What It Tells You | Healthy Target |
|--------|-------------------|----------------|
| **Total Patients** | Unique patients in the system | Growth indicates expanding reach |
| **Total Encounters** | All clinical visits/admissions | Higher volume = higher utilization |
| **Readmission Rate** | % of patients readmitted within 30 days | <15% (CMS penalty threshold) |
| **ICU Admission Rate** | % of encounters requiring ICU | Lower is better; benchmark ~10-15% |
| **Avg Length of Stay** | Mean days per hospital stay | 4-6 days typical for acute care |
| **Quality Compliance** | % of clinical quality measures met | >80% forCMS Star Rating |

---

## Analytics Panels

### Panel 1: Readmission Risk by Hospital

**Chart Type:** Horizontal bar chart
**What It Shows:** Readmission rate for each hospital, color-coded by severity.

| Color | Meaning |
|-------|---------|
| Green | Readmission rate < 25% (good) |
| Orange | Readmission rate 25-50% (needs attention) |
| Red | Readmission rate > 50% (critical) |

**Why It Matters:**
- CMS penalizes hospitals with excess readmissions (HRRP program)
- High readmission rates signal gaps in discharge planning, follow-up care, or care coordination
- Allows side-by-side comparison across the hospital network

**How to Use:**
1. Identify the hospital with the highest readmission rate
2. Investigate root causes: inadequate discharge instructions? lack of follow-up appointments? social determinants?
3. Benchmark against the network average (dashed line)
4. Set improvement targets and track monthly

---

### Panel 2: Surgical DRG Profitability

**Chart Type:** Horizontal bar chart (diverging)
**What It Shows:** Average profit (or loss) per surgical case by DRG (Diagnosis Related Group).

| Color | Meaning |
|-------|---------|
| Green | Profitable procedures (positive margin) |
| Red | Loss-making procedures (negative margin) |

**Why It Matters:**
- Identifies which procedures drain financial resources
- Guides contract renegotiation with payers
- Informs resource allocation and surgical scheduling decisions
- Critical for margin management in value-based care

**How to Use:**
1. Focus on the largest red bars — these are the biggest money losers
2. Compare volume (n=) with per-case loss to find total financial impact
3. Investigate: Is the loss due to high supply costs? prolonged LOS? low reimbursement?
4. For profitable DRGs: ensure capacity and throughput to maximize revenue

---

### Panel 3: Quality Measure Compliance

**Chart Type:** Horizontal bar chart with threshold lines
**What It Shows:** Compliance rate for each clinical quality measure being tracked.

| Threshold | Meaning |
|-----------|---------|
| Red dashed line (50%) | Below this = significant quality gap |
| Green dashed line (75%) | CMS target for payment incentives |

**Why It Matters:**
- Directly impacts CMS reimbursement (MIPS/MACRA)
- Affects hospital star ratings and public reporting
- Patient safety and outcomes depend on measure compliance
- Non-compliance exposes the organization to financial penalties

**How to Use:**
1. Immediately address measures below 50% — these are red flags
2. Prioritize measures closest to the 75% target — easiest to push over the finish line
3. Investigate system-level barriers: EHR workflow gaps, staff training, patient engagement
4. Track improvement quarter-over-quarter

---

### Panel 4: Hospital Performance Benchmarking

**Chart Type:** Grouped bar chart
**What It Shows:** Three key metrics side-by-side for each hospital: Readmission Rate, ICU Rate, and Average Length of Stay.

| Metric | Ideal Direction |
|--------|----------------|
| Readmission Rate | Lower is better |
| ICU Rate | Lower is better (indicates appropriate triage) |
| Avg LOS | Lower is better (indicates efficient throughput) |

**Why It Matters:**
- Enables apples-to-apples comparison across facilities
- Identifies best practices from top performers
- Highlights outlier hospitals needing intervention
- Supports data-driven capital and staffing decisions

**How to Use:**
1. Find the hospital with the best overall profile (low on all three)
2. Study their processes — what are they doing differently?
3. Find the hospital with the worst profile — deploy improvement resources there
4. Consider case-mix differences when interpreting results

---

## AI Chatbot

**Location:** Bottom of the dashboard
**Purpose:** Enable stakeholders to query the database using natural language

**Example Questions:**
- "How many patients were admitted in June?"
- "What is the average cost of Caesarean sections?"
- "Show me all patients with LACE score above 15"
- "Which department has the most encounters?"
- "What is the readmission rate for ICU patients?"

**How It Works:**
1. Type your question in the chat input
2. The AI converts your question to SQL
3. The query runs against the live database
4. Results are displayed with a natural language summary

---

## Data Source Notes

- **Patient data** includes demographics, LACE risk scores, and geographic information
- **Encounter data** covers admissions, discharges, LOS, ICU stays, and readmission flags
- **Surgical data** includes all obstetric cases with cost, profit, and DRG details
- **Quality data** tracks 6 clinical measures across two time periods (2015-2016)
- **Financial data** covers charges, payments, adjustments, and outstanding balances

---

## Recommended Review Cadence

| Audience | Frequency | Focus |
|----------|-----------|-------|
| Executive Leadership | Monthly | KPI trends, financial performance |
| Clinical Operations | Weekly | Readmission rates, quality compliance |
| Finance Team | Monthly | DRG profitability, collection rates |
| Quality Committee | Quarterly | Measure compliance trends, benchmarking |
