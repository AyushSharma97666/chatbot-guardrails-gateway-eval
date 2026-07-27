"""
Physically read-only access to HealthcareDB.db.

This is the only module the chat pipeline should use to touch the
analytics database. Unlike excel_to_sql.py's ExcelToSQL (a normal
read-write connection), the connection here is opened in SQLite's
URI mode=ro, so even a validator bypass would be rejected by SQLite
itself at the driver level, not just by application logic.
"""

import os
import sys
import time
import sqlite3
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from utils.logger import get_logger

logger = get_logger("readonly_db")


def get_readonly_connection(db_path: str = None) -> sqlite3.Connection:
    db_path = db_path or config.DATABASE_PATH
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def execute_readonly_query(sql: str, db_path: str = None) -> dict:
    """
    Runs sql against a physically read-only connection.
    Returns {"success", "df", "row_count", "error"}.
    Caller is responsible for having already validated sql — this function
    does not itself check for SELECT-only; the read-only connection is the
    enforcement mechanism, so an attempted write simply fails here.
    """
    result = {"success": False, "df": None, "row_count": 0, "error": None}
    start = time.perf_counter()

    conn = None
    try:
        conn = get_readonly_connection(db_path)
        df = pd.read_sql_query(sql, conn)
        result["success"] = True
        result["df"] = df
        result["row_count"] = len(df)
        logger.info(f"Read-only query executed: {result['row_count']} rows in {time.perf_counter() - start:.3f}s")
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Read-only query failed: {e}")
    finally:
        if conn is not None:
            conn.close()

    return result
