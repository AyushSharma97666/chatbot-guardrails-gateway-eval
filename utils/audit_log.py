"""
Structured, queryable audit log — separate from utils/logger.py's
free-text debug log at logs/app_YYYYMMDD.log.

Deliberately never stores row-level query results (PHI). Stores only
question text, generated SQL, validator verdict, counts, and timing —
enough to reconstruct what happened without becoming a PHI leak itself.
Read by pages/1_Evaluation.py for latency/cost/cache trend charts, and
by evaluation/run_eval.py to link eval case results back to the run
that produced them.
"""

import os
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import system_db
from utils.logger import get_logger

logger = get_logger("audit_log")

_COLUMNS = [
    "timestamp", "question", "normalized_question", "generated_sql",
    "validator_verdict", "validator_reason", "executed", "row_count",
    "masked_columns", "groundedness_ok", "cache_hit", "narration_cache_hit",
    "latency_ms", "prompt_tokens", "completion_tokens", "estimated_cost_usd",
    "source", "error",
]


def log_event(**fields) -> int:
    system_db.ensure_initialized()
    fields.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    fields.setdefault("executed", 0)
    fields.setdefault("cache_hit", 0)
    fields.setdefault("narration_cache_hit", 0)
    row = {col: fields.get(col) for col in _COLUMNS}

    conn = system_db.get_connection()
    try:
        cursor = conn.execute(
            f"INSERT INTO audit_log ({', '.join(_COLUMNS)}) VALUES ({', '.join('?' for _ in _COLUMNS)})",
            [row[c] for c in _COLUMNS],
        )
        conn.commit()
        event_id = cursor.lastrowid
        logger.debug(f"Audit event logged: id={event_id} source={row['source']} verdict={row['validator_verdict']}")
        return event_id
    finally:
        conn.close()


def fetch_recent(limit: int = 50, source: str = None) -> pd.DataFrame:
    system_db.ensure_initialized()
    conn = system_db.get_connection()
    try:
        if source:
            return pd.read_sql_query(
                "SELECT * FROM audit_log WHERE source = ? ORDER BY id DESC LIMIT ?",
                conn, params=(source, limit),
            )
        return pd.read_sql_query("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", conn, params=(limit,))
    finally:
        conn.close()


def compute_cache_hit_rate(source: str = "chat_ui") -> float:
    system_db.ensure_initialized()
    conn = system_db.get_connection()
    try:
        row = conn.execute(
            "SELECT AVG(cache_hit) FROM audit_log WHERE source = ? AND executed = 1",
            (source,),
        ).fetchone()
        return float(row[0]) if row and row[0] is not None else 0.0
    finally:
        conn.close()


def compute_latency_trend(bucket: str = "day", source: str = "chat_ui") -> pd.DataFrame:
    df = fetch_recent(limit=5000, source=source)
    if df.empty:
        return pd.DataFrame(columns=["bucket", "avg_latency_ms", "p50_latency_ms", "p95_latency_ms", "count"])

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["bucket"] = df["timestamp"].dt.date if bucket == "day" else df["timestamp"].dt.floor("h")

    grouped = df.groupby("bucket")["latency_ms"].agg(
        avg_latency_ms="mean",
        p50_latency_ms=lambda s: s.quantile(0.5),
        p95_latency_ms=lambda s: s.quantile(0.95),
        count="count",
    ).reset_index()
    return grouped


def compute_token_cost_trend(bucket: str = "day", source: str = "chat_ui") -> pd.DataFrame:
    df = fetch_recent(limit=5000, source=source)
    if df.empty:
        return pd.DataFrame(columns=["bucket", "total_tokens", "estimated_cost_usd"])

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["bucket"] = df["timestamp"].dt.date if bucket == "day" else df["timestamp"].dt.floor("h")
    df["total_tokens"] = df[["prompt_tokens", "completion_tokens"]].fillna(0).sum(axis=1)

    grouped = df.groupby("bucket").agg(
        total_tokens=("total_tokens", "sum"),
        estimated_cost_usd=("estimated_cost_usd", "sum"),
    ).reset_index()
    return grouped
