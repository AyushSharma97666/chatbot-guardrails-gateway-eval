"""
Warn-only hallucination check for the chatbot's narrated response.

Confirms every number the narration states actually appears somewhere in
the query result data (or matches the row/column count, to avoid false
positives on phrasing like "found 42 results"). Never blocks a response —
only logs a warning — since number-matching against LLM-paraphrased text
is inherently heuristic (rounding, unit conversion, etc.).
"""

import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.logger import get_logger

logger = get_logger("groundedness")

_NUMBER_RE = re.compile(r"-?\$?\d[\d,]*\.?\d*%?")


def extract_numbers(text: str) -> list:
    if not text:
        return []

    numbers = []
    for match in _NUMBER_RE.findall(text):
        cleaned = match.replace("$", "").replace(",", "").replace("%", "")
        try:
            numbers.append(float(cleaned))
        except ValueError:
            continue
    return numbers


def extract_numbers_from_df(df: pd.DataFrame) -> set:
    values = set()
    if df is None or df.empty:
        return values

    for col in df.columns:
        numeric = pd.to_numeric(df[col], errors="coerce")
        for v in numeric.dropna():
            values.add(round(float(v), 2))
    return values


def check_groundedness(narration: str, df: pd.DataFrame, row_count: int, tolerance: float = 0.01) -> tuple:
    """Returns (is_grounded, unmatched_numbers)."""
    narration_numbers = extract_numbers(narration)
    if not narration_numbers:
        return True, []

    allowed = extract_numbers_from_df(df)
    allowed.add(float(row_count))
    if df is not None:
        allowed.add(float(len(df.columns)))
        allowed.add(float(len(df)))

    unmatched = [
        n for n in narration_numbers
        if not any(abs(n - a) <= max(tolerance * max(abs(a), 1), 0.5) for a in allowed)
    ]

    is_grounded = len(unmatched) == 0
    if not is_grounded:
        logger.warning(f"Groundedness check failed: numbers in narration not found in query results: {unmatched}")

    return is_grounded, unmatched
