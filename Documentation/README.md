# Text-to-SQL Healthcare Chatbot & Dashboard

A Streamlit application that turns raw hospital Excel exports into a queryable SQLite
database, then exposes that data through (1) a healthcare KPI dashboard, (2) a
natural-language chatbot that converts questions into SQL using Google Gemini behind a
safety gateway (validation, read-only execution, PII masking, caching, audit logging),
and (3) an Evaluation & Safety dashboard that regression-tests both correctness and
guardrail behavior.

## End-to-End Data Flow: Excel → SQLite → Dashboard / Chatbot Gateway

```
excel_files/*.xlsx                    (raw hospital data exports, one file per table)
        |
        |  pandas.read_excel()
        v
excel_to_sql.py (ExcelToSQL class)    (import_excel_to_sql: df.to_sql(if_exists="replace"))
        |
        v
database/HealthcareDB.db              (single SQLite file, one table per Excel file)
        |
        +──────────────────────────────┬──────────────────────────────────────────┐
        v                               v                                          v
app.py: load_all_data()/query_db()   app.py chat input                  evaluation/run_eval.py
        |                               |                                          |
        v                               v                                          v
Streamlit KPI dashboard      utils/chat_gateway.ask_question()  <───────  golden_set.json /
(KPI cards + Plotly charts)            |        (the ONLY chokepoint —          adversarial_set.json
                                        |        nothing reaches Gemini or
                                        |        the DB except through here)
                                        v
                         1. utils/query_cache.lookup()  (exact-match, Phase 3 "memory")
                              hit  -> utils/sql_guardrail.validate_sql() re-check
                              miss -> utils/gemini_utils.get_gemini_response(sql_generator)
                                      -> extract_sql_from_response()
                                      -> utils/sql_guardrail.validate_sql()
                                         invalid -> BLOCKED, audit-logged, generic refusal
                                        v
                         2. utils/readonly_db.execute_readonly_query()
                              (physically read-only SQLite connection — always
                               re-runs fresh, cache hit or not)
                                        v
                         3. utils/pii_guard.mask_dataframe()
                              (drops config.SENSITIVE_COLUMNS before display AND
                               before the narration prompt is built)
                                        v
                         4. query_cache.store()/touch_hit()   (source="chat_ui" only —
                                                                 eval traffic never pollutes it)
                                        v
                         5. narration: reused from cache (if still fresh vs. last DB
                            rebuild) OR utils/gemini_utils.generate_chatbot_response()
                                        v
                         6. utils/groundedness.check_groundedness()  (warn-only)
                                        v
                         7. utils/audit_log.log_event()  -> database/system.db
                            (question, SQL, verdict, row count, latency, tokens —
                             NEVER row-level data)
                                        v
                         Natural-language answer + masked data table in chat UI
```

**In short:** Excel workbooks are loaded into a SQLite database (one file = one table),
and `app.py` (Streamlit) reads from that database directly for dashboard charts, but
every chatbot question is routed through `utils/chat_gateway.ask_question()` — a single
chokepoint that checks an exact-match cache, generates and validates SQL, executes it
against a physically read-only connection, masks PII columns, narrates the result
(reusing cached narration when safe to), runs a hallucination check, and writes a
structured audit-log entry, all before anything reaches the chat UI. A separate
Evaluation & Safety page (`pages/1_Evaluation.py`) runs a golden correctness set and an
adversarial safety set through that same gateway on demand.

## Folder Structure

```
Text_to_SQL_ChatBot/
├── app.py                     # Streamlit entrypoint: dashboard + chatbot UI (flat script, no main())
├── excel_to_sql.py            # ExcelToSQL class: Excel import + generic query engine
├── requirement.txt            # Python dependencies
├── .env                       # GOOGLE_API_KEY / GEMINI_API_KEY, DEBUG (not committed)
│
├── config/
│   └── config.py              # Loads .env; model/paths/PII/cache/pricing settings
│
├── excel_files/                # Source data - one .xlsx per SQL table
│   ├── dbo.Accounts.xlsx  … dbo.Vitals.xlsx   (13 files, see Step 1)
│
├── database/
│   ├── HealthcareDB.db        # Analytics SQLite database produced from excel_files/
│   └── system.db              # NEW — audit_log, query_cache, eval_runs, eval_case_results
│                                 (kept in a separate file so nothing here can ever
│                                  touch/corrupt the analytics data)
│
├── utils/
│   ├── loadData_to_DB.py      # loadData_inDB (single file) + rebuild_database_from_excel
│   │                             (folder-wide rebuild — currently not wired to any UI button)
│   ├── data_extraction.py     # Query helpers; extract_data_with_query now SQL-guardrail-checked
│   ├── gemini_utils.py        # GeminiClient: NL->SQL + NL narration, now with token-usage capture
│   ├── logger.py              # Shared free-text debug logger -> logs/app_YYYYMMDD.log
│   ├── system_db.py           # NEW — schema owner + connection for database/system.db
│   ├── sql_guardrail.py       # NEW — SELECT/WITH-only validator (Phase 0 guardrail)
│   ├── readonly_db.py         # NEW — physically read-only connection to HealthcareDB.db
│   ├── pii_guard.py           # NEW — drops config.SENSITIVE_COLUMNS from chatbot results
│   ├── groundedness.py        # NEW — warn-only hallucination check on narrated answers
│   ├── audit_log.py           # NEW — structured, queryable audit log (separate from logger.py)
│   ├── query_cache.py         # NEW — exact-match question->SQL cache (Phase 3 "memory")
│   └── chat_gateway.py        # NEW — ask_question(): the single chokepoint, see flow above
│
├── evaluation/                 # NEW — correctness + safety regression suite
│   ├── golden_set.json         # ~18 known-good questions with expected SQL/row-count checks
│   ├── adversarial_set.json    # ~15 injection/DML/PII-fishing prompts with expected outcomes
│   └── run_eval.py             # run_full_suite(): drives both sets through chat_gateway,
│                                  writes results to database/system.db
│
├── pages/                       # NEW — Streamlit multipage folder (auto-appears in sidebar nav)
│   └── 1_Evaluation.py          # Evaluation & Safety dashboard: run suite, pass-rate tiles,
│                                   results tables, trend charts, cache stats
│
├── prompts/
│   └── system_prompts/
│       ├── sql_generator.txt          # System prompt + full schema used for NL->SQL
│       ├── chatbot.txt                # System prompt used to narrate query results
│       └── data_base_structure.txt    # Scratch notes on schema-lookup strategy
│
├── logs/
│   └── app_YYYYMMDD.log       # Daily free-text debug log (see utils/logger.py)
│
└── Documentation/
    ├── README.md                          # This file
    ├── database_realated document.txt     # Raw column list per table (source of truth for columns)
    ├── feedback_4_jun_2026.txt            # Working notes
    └── ChatGPT Image *.png                # Reference/design images
```

## Step 1 — Excel Files (`excel_files/`)

Thirteen `.xlsx` workbooks, each representing one SQL Server table (`dbo.<TableName>`)
exported from the source hospital system: `Accounts`, `Departments`, `Encounters`,
`Hospitals`, `OrdersProcedures`, `Patients`, `Physicians`, `Practices`,
`QualityMeasureData`, `Results`, `SurgicalCosts`, `SurgicalEncounters`, `Vitals`.

## Step 2 — Loading Excel into SQLite

- **`excel_to_sql.py`** — defines `ExcelToSQL`, the core class used everywhere:
  - `import_excel_to_sql(excel_path, table_name)` reads the workbook with
    `pandas.read_excel` and writes it to SQLite via `df.to_sql(if_exists="replace")`.
  - `execute_query(query, params=None, allow_write=True)` — generic SQLite execution.
    **New `allow_write` parameter**: when `False`, the query is run through
    `utils/sql_guardrail.validate_sql()` first and refused if it isn't a safe SELECT —
    this is what closes the gap where any non-SELECT statement used to be silently
    `commit()`ted. Defaults to `True` so the existing interactive CLI in `main()` keeps
    working unchanged.
  - Running the file directly (`python excel_to_sql.py`) drops into an interactive
    SQL REPL against `HealthcareDB.db`.
- **`utils/loadData_to_DB.py`** — `loadData_inDB(...)` loads one Excel file/table pair.
  `rebuild_database_from_excel(excel_folder=None, db_name=None)` rebuilds **all**
  tables from every `dbo.*.xlsx` file in `excel_files/` in one call, returning a
  per-table `{file, table, rows, status, error}` summary. This function is fully
  working but currently has no UI button wired to it (an earlier dashboard revision
  had one; the current `app.py` doesn't) — call it directly if you need to refresh
  the whole database from Excel.

Each Excel file becomes exactly one table in `database/HealthcareDB.db`. Re-importing
replaces the table (`if_exists="replace"`) — a full refresh, not an incremental load.

> Note: both `excel_to_sql.py` (`__main__`) and `utils/loadData_to_DB.py`'s module-level
> constants still reference a hardcoded, machine-specific path left over from
> development. Call `loadData_inDB(...)` / `rebuild_database_from_excel(...)` directly
> with the current `excel_files/` folder rather than relying on those defaults.

## Step 3 — Database Schema (`database/HealthcareDB.db`)

Central entities and how they relate (full column-level detail lives in
[`prompts/system_prompts/sql_generator.txt`](../prompts/system_prompts/sql_generator.txt)
and the raw column dump in
[`database_realated document.txt`](database_realated document.txt)):

| Table | Primary Key | Key Relationships |
|---|---|---|
| `Patients` | Master Patient ID | referenced by Encounters, Results, SurgicalEncounters, QualityMeasureData |
| `Encounters` | Patient Encounter ID | → Patients, Departments, Accounts, Physicians (Admitting/Discharging/Attending Provider ID) |
| `Accounts` | Hospital Account ID | ← Encounters.Hospital Account ID |
| `Departments` | Department ID | → Hospitals.Hospital ID |
| `Hospitals` | Hospital ID | ← Departments, QualityMeasureData |
| `Physicians` | Provider ID | referenced by Encounters, OrdersProcedures, SurgicalEncounters, QualityMeasureData |
| `OrdersProcedures` | — | → Encounters.Patient Encounter ID, Physicians.Provider ID |
| `Vitals` | — | → Encounters.Patient Encounter ID |
| `Results` | — | → Patients.Master Patient ID |
| `SurgicalEncounters` | Surgery ID | → Patients.Master Patient ID, Physicians.Provider ID (Surgeon ID) |
| `SurgicalCosts` | Surgical Cost ID | → SurgicalEncounters.Surgery ID |
| `QualityMeasureData` | — | → Patients, Hospitals, Physicians, Practices |
| `Practices` | Practice ID | ← QualityMeasureData.Practice ID |

This schema (minus `SurgicalCosts`, still not documented in the prompt file itself) is
embedded directly into the Gemini SQL-generation system prompt. `golden_12` in
`evaluation/golden_set.json` deliberately exercises `SurgicalCosts` to catch regressions
caused by that documentation gap.

## Step 4a — Dashboard (`app.py`)

`app.py` is a flat, top-to-bottom Streamlit script (no `main()`). `load_all_data()`
(`@st.cache_data(ttl=300)`) loads 11 tables, computes derived columns (`Age`, `Readmit`,
`ICU`, `Surgical Profit Margin %`, `Compliant`), and builds an hospital-linked
encounters frame. The dashboard renders:

- A KPI banner (Total Patients, Total Encounters, Readmission Rate, ICU Rate, Avg LOS,
  Quality Compliance).
- **Readmission Risk by Hospital**, **Surgical DRG Profitability**, **Quality Measure
  Compliance**, and **Hospital Performance Benchmarking** chart sections (Plotly).
- A sidebar with database-last-updated info and quick stats.

*(Known, out-of-scope minor issues: `query_db()` is defined but never called; `Vitals`
is referenced via `tables.get("Vitals", ...)` without ever being fetched into `tables`,
so it's always empty — neither affects the chatbot/guardrail work below.)*

## Step 4b — Chatbot & Safety Gateway (`utils/chat_gateway.ask_question()`)

The chat UI in `app.py` no longer talks to Gemini or the database directly — it calls
`ask_question(user_input)` and renders whatever comes back. Internally:

1. **Cache check** (`utils/query_cache.py`, exact-match only): if this exact question
   (normalized) was answered before, its cached SQL is pulled and **re-validated**
   before reuse — a defense-in-depth check in case a cached row was ever bad.
2. **SQL generation** (cache miss only): `get_gemini_response(..., prompt_name="sql_generator")`
   → `extract_sql_from_response()` (its unsafe fallback now only recognizes
   `SELECT`/`WITH` lines, never `INSERT/UPDATE/DELETE/CREATE/ALTER/DROP`).
3. **Validation** (`utils/sql_guardrail.validate_sql()`): strips comments/string-literal
   contents first (so a literal like `'Deleted Patient'` or a column like
   `created_date` can't false-positive), rejects anything that isn't a single
   `SELECT`/`WITH` statement, and rejects on a word-boundary match against a hardcoded
   forbidden-keyword list (`INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, ATTACH,
   DETACH, PRAGMA, REPLACE, TRUNCATE, EXEC, EXECUTE, VACUUM, REINDEX, GRANT, REVOKE`).
   Anything invalid is blocked with a generic refusal — the specific validator reason
   is logged but never shown to the user.
4. **Execution** (`utils/readonly_db.execute_readonly_query()`): opens
   `HealthcareDB.db` via a SQLite URI in `mode=ro` — even a validator bypass would be
   rejected by SQLite itself. Runs **fresh every time**, cache hit or not, so a
   database rebuild is always reflected in the numbers.
5. **PII masking** (`utils/pii_guard.mask_dataframe()`): drops any column in
   `config.SENSITIVE_COLUMNS` before the result is shown to the user **or** used to
   build the narration prompt — so masked columns never reach Google's API either.
6. **Cache write** (`chat_ui` traffic only — eval runs pass `bypass_cache=True` and
   never pollute the real cache with synthetic questions).
7. **Narration**: reused from the cache if it's still newer than `HealthcareDB.db`'s
   last-modified time (see `is_narration_fresh`), otherwise
   `generate_chatbot_response(..., prompt_name="chatbot")` is called fresh.
8. **Groundedness check** (`utils/groundedness.check_groundedness()`): confirms every
   number in the narration appears in the query results; warn-only, never blocks.
9. **Audit log** (`utils/audit_log.log_event()` → `database/system.db`): records the
   question, generated SQL, validator verdict/reason, row count, cache-hit flags,
   latency, token counts, and estimated cost — **never** row-level data.

## Guardrails & Safety Layer (`utils/`)

| Module | Responsibility |
|---|---|
| `sql_guardrail.py` | The core validator described above — pure function, no I/O. |
| `readonly_db.py` | Physically read-only SQLite connection; the only way the chat path touches `HealthcareDB.db`. |
| `pii_guard.py` | Drops `config.SENSITIVE_COLUMNS` (Patient Name/DOB/Address/Lat-Long — direct identifiers only; quasi-identifiers like Gender/Ethnicity stay visible since the dashboard aggregates on them). Toggle via `config.PII_MASK_ENABLED`. |
| `groundedness.py` | Warn-only hallucination check on narrated answers. |
| `chat_gateway.py` | Wires all of the above into `ask_question()`, the single chokepoint. |

## Caching (`utils/query_cache.py`) — Phase 3 "memory"

Exact-match only (no fuzzy/semantic matching by design — deferred until real usage
data justifies it). Stores `normalized_question -> validated_sql` plus the last
narration and its timestamp in `database/system.db`. **Hard rule: only SQL that has
already passed `sql_guardrail.validate_sql()` is ever cached** — the cache is a
shortcut around SQL *generation*, never around *validation or execution*. Toggle via
`config.CACHE_ENABLED`.

## Audit Logging (`utils/audit_log.py`)

Separate from `utils/logger.py`'s free-text debug log. Structured, queryable rows in
`database/system.db`'s `audit_log` table — deliberately excludes row-level query
results (PHI) and stores only question text, generated SQL, validator verdict, counts,
timing, and token/cost estimates. Powers the trend charts on the Evaluation page via
`fetch_recent()`, `compute_cache_hit_rate()`, `compute_latency_trend()`, and
`compute_token_cost_trend()`.

## Evaluation Suite (`evaluation/`, `pages/1_Evaluation.py`)

- **`golden_set.json`** (18 cases) — known questions spanning aggregation, filter,
  join, trend, top-N, and edge-case categories, each checked for execution success,
  expected SQL substrings, and/or expected row count.
- **`adversarial_set.json`** (15 cases) — DML/DDL attempts, multi-statement stacking,
  prompt-injection framing, PII-fishing, and case-evasion prompts, each with an
  `expected_outcome` of `blocked`, `redacted` (executes but sensitive columns are
  stripped), or `allowed` (a harmless query, e.g. one with an inert SQL comment, that
  should correctly pass through rather than being over-blocked).
- **`run_eval.py`** — `run_full_suite()` drives every case through
  `chat_gateway.ask_question(source="eval_golden"/"eval_adversarial", bypass_cache=True)`
  — the exact same chokepoint real chat traffic uses — and writes results to
  `eval_runs`/`eval_case_results` in `database/system.db`. Runnable standalone:
  `python evaluation/run_eval.py`.
- **`pages/1_Evaluation.py`** — a genuinely separate Streamlit script (Streamlit's
  `pages/` multipage convention auto-adds it to the sidebar nav). Has a one-click **Run
  Evaluation Now** button (no confirm step — it's non-destructive, read-only, and only
  appends eval rows), stat tiles for correctness/safety pass rates, cache hit rate, and
  average latency, per-case result tables, and pass-rate/cost trend charts.

## Configuration (`config/config.py`)

- `GEMINI_API_KEY` (from `GEMINI_API_KEY` or `GOOGLE_API_KEY` env var)
- `GEMINI_MODEL` = `gemini-2.5-pro`, `TEMPERATURE` = 0.7, `MAX_OUTPUT_TOKENS` = 2048
- `PROMPTS_FOLDER`, `DATABASE_PATH`, `EXCEL_FOLDER` — as before
- **`SYSTEM_DB_PATH`** = `database/system.db` — audit log, cache, eval results
- **`SENSITIVE_COLUMNS`** — the PII column deny-list used by `pii_guard.py`
- **`PII_MASK_ENABLED`** / **`CACHE_ENABLED`** — feature toggles
- **`GEMINI_PRICE_PER_1K_INPUT_TOKENS`** / **`..._OUTPUT_TOKENS`** — *estimated* pricing
  constants used only for the Evaluation page's cost trend chart, not billing-accurate
- `DEBUG` from env

`.env` (not committed, see `.gitignore`) must define `GOOGLE_API_KEY`.

## Running the Project

```bash
# 1. Install dependencies
pip install -r requirement.txt

# 2. Set your Gemini API key
echo "GOOGLE_API_KEY=your_key_here" > .env

# 3. (Re)build the database from the Excel files, if HealthcareDB.db needs a refresh
python -c "from utils.loadData_to_DB import rebuild_database_from_excel; print(rebuild_database_from_excel())"

# 4. Launch the dashboard + chatbot (the Evaluation page appears automatically in the sidebar)
streamlit run app.py

# 5. Optional: run the correctness/safety suite from the command line
python evaluation/run_eval.py
```

## Logging

Two separate logs, deliberately not merged:

- **`utils/logger.py`** — free-text debug log (`healthcare_app` logger) writing to both
  the console and a daily file at `logs/app_YYYYMMDD.log`. Every module logs under this
  namespace via `get_logger(<module>)`.
- **`utils/audit_log.py`** — structured, queryable compliance/eval log in
  `database/system.db`, described above. Never contains row-level query data, so it's
  safe to retain/query long-term in a way the debug log isn't.
