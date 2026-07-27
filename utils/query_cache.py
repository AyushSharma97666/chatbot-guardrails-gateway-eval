"""
Exact-match question -> SQL cache (Phase 3 "memory").

No fuzzy/semantic matching — deliberately deferred until real usage data
shows exact-match isn't catching enough repeat questions.

Hard rule: store() must only ever be called with SQL that has already
passed utils.sql_guardrail.validate_sql(). The cache is a shortcut around
SQL *generation*, never around *validation or execution* — every cache
hit still gets re-executed fresh against the live database (see
chat_gateway.py); only the narration text is conditionally reused, and
only while it's still fresh relative to the last database rebuild.
"""

import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from utils import system_db
from utils.logger import get_logger

logger = get_logger("query_cache")


def normalize_question(text: str) -> str:
    if not text:
        return ""
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return normalized.rstrip("?.!").strip()


def lookup(question: str):
    system_db.ensure_initialized()
    normalized = normalize_question(question)
    if not normalized:
        return None

    conn = system_db.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM query_cache WHERE normalized_question = ?", (normalized,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def store(question: str, sql: str, source: str = "auto"):
    system_db.ensure_initialized()
    normalized = normalize_question(question)
    if not normalized:
        return None

    now = datetime.now(timezone.utc).isoformat()
    conn = system_db.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO query_cache
                (normalized_question, original_question, validated_sql, hit_count, source, created_at, last_used_at)
            VALUES (?, ?, ?, 0, ?, ?, ?)
            ON CONFLICT(normalized_question) DO UPDATE SET
                validated_sql = excluded.validated_sql,
                last_used_at = excluded.last_used_at
            """,
            (normalized, question, sql, source, now, now),
        )
        conn.commit()
        logger.info(f"Cached question -> SQL (source={source}): {question[:80]}")
    finally:
        conn.close()

    return lookup(question)


def touch_hit(entry_id: int) -> None:
    system_db.ensure_initialized()
    now = datetime.now(timezone.utc).isoformat()
    conn = system_db.get_connection()
    try:
        conn.execute(
            "UPDATE query_cache SET hit_count = hit_count + 1, last_used_at = ? WHERE id = ?",
            (now, entry_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_narration(entry_id: int, narration: str) -> None:
    system_db.ensure_initialized()
    now = datetime.now(timezone.utc).isoformat()
    conn = system_db.get_connection()
    try:
        conn.execute(
            "UPDATE query_cache SET last_narration = ?, narration_generated_at = ? WHERE id = ?",
            (narration, now, entry_id),
        )
        conn.commit()
    finally:
        conn.close()


def is_narration_fresh(entry: dict, db_path: str = None) -> bool:
    if not entry or not entry.get("narration_generated_at") or not entry.get("last_narration"):
        return False

    db_path = db_path or config.DATABASE_PATH
    if not os.path.exists(db_path):
        return False

    # Both sides must be timezone-aware UTC: narration_generated_at is written
    # with datetime.now(timezone.utc), so the file mtime has to be converted
    # the same way (a naive datetime.fromtimestamp() would use local time and
    # silently skew the comparison, or raise when compared to an aware value).
    db_mtime = datetime.fromtimestamp(os.path.getmtime(db_path), tz=timezone.utc)
    try:
        narration_time = datetime.fromisoformat(entry["narration_generated_at"])
    except ValueError:
        return False

    return narration_time >= db_mtime


def get_cache_stats() -> dict:
    system_db.ensure_initialized()
    conn = system_db.get_connection()
    try:
        total_entries = conn.execute("SELECT COUNT(*) FROM query_cache").fetchone()[0]
        total_hits = conn.execute("SELECT COALESCE(SUM(hit_count), 0) FROM query_cache").fetchone()[0]
        top = conn.execute(
            "SELECT original_question, hit_count, source FROM query_cache ORDER BY hit_count DESC LIMIT 10"
        ).fetchall()
        return {
            "total_entries": total_entries,
            "total_hits": total_hits,
            "top_questions": [dict(r) for r in top],
        }
    finally:
        conn.close()
