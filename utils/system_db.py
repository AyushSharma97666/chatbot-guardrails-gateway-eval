"""
Schema owner and connection helper for database/system.db.

Holds audit log, query cache, and evaluation results — kept in a
separate physical file from HealthcareDB.db so nothing this module
writes can ever touch/corrupt the analytics data.
"""

import os
import sys
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config

_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        question TEXT NOT NULL,
        normalized_question TEXT,
        generated_sql TEXT,
        validator_verdict TEXT NOT NULL,
        validator_reason TEXT,
        executed INTEGER NOT NULL DEFAULT 0,
        row_count INTEGER,
        masked_columns TEXT,
        groundedness_ok INTEGER,
        cache_hit INTEGER NOT NULL DEFAULT 0,
        narration_cache_hit INTEGER NOT NULL DEFAULT 0,
        latency_ms INTEGER,
        prompt_tokens INTEGER,
        completion_tokens INTEGER,
        estimated_cost_usd REAL,
        source TEXT NOT NULL,
        error TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS query_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        normalized_question TEXT NOT NULL UNIQUE,
        original_question TEXT NOT NULL,
        validated_sql TEXT NOT NULL,
        last_narration TEXT,
        narration_generated_at TEXT,
        hit_count INTEGER NOT NULL DEFAULT 0,
        source TEXT NOT NULL DEFAULT 'auto',
        created_at TEXT NOT NULL,
        last_used_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS eval_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        suite TEXT NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        total_cases INTEGER,
        passed INTEGER,
        failed INTEGER,
        pass_rate REAL,
        triggered_by TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS eval_case_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        suite TEXT NOT NULL,
        case_id TEXT NOT NULL,
        question TEXT NOT NULL,
        expected TEXT,
        actual_sql TEXT,
        actual_outcome TEXT,
        passed INTEGER NOT NULL,
        detail TEXT,
        latency_ms INTEGER,
        audit_log_id INTEGER
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_source ON audit_log(source)",
    "CREATE INDEX IF NOT EXISTS idx_eval_case_results_run_id ON eval_case_results(run_id)",
]

_initialized = False


def get_connection() -> sqlite3.Connection:
    db_path = getattr(config, "SYSTEM_DB_PATH", "database/system.db")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection = None) -> None:
    global _initialized
    owns_conn = conn is None
    conn = conn or get_connection()
    try:
        cursor = conn.cursor()
        for statement in _SCHEMA_STATEMENTS:
            cursor.execute(statement)
        conn.commit()
        _initialized = True
    finally:
        if owns_conn:
            conn.close()


def ensure_initialized() -> None:
    """Cheap idempotent guard other modules call before their first query."""
    if not _initialized:
        init_schema()
