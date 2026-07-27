"""
PII column masking for chatbot query results.

Drops (not redacts) any column matching config.SENSITIVE_COLUMNS before
the result is shown to the user OR used to build the Gemini narration
context — masking after narration is built would be too late, since the
data would have already left the network boundary to Google's API.
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config


def mask_dataframe(df: pd.DataFrame) -> tuple:
    """Returns (masked_df, dropped_columns)."""
    if df is None or df.empty:
        return df, []

    if not getattr(config, "PII_MASK_ENABLED", True):
        return df, []

    sensitive = {c.lower() for c in getattr(config, "SENSITIVE_COLUMNS", [])}
    dropped = [c for c in df.columns if c.lower() in sensitive]

    if not dropped:
        return df, []

    return df.drop(columns=dropped), dropped
