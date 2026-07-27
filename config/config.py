
"""
Configuration settings for the application
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

# Model Configuration
GEMINI_MODEL = "gemini-2.5-pro"  # or "gemini-1.5-pro" for latest
TEMPERATURE = 0.7
MAX_OUTPUT_TOKENS = 2048

# Paths
PROMPTS_FOLDER = "prompts/system_prompts"
DATABASE_PATH = "database/HealthcareDB.db"
EXCEL_FOLDER = "excel_files"
SYSTEM_DB_PATH = "database/system.db"  # audit log, query cache, eval results

# Application Settings
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# ─────────────────────────────────────────────────────────────
# Chatbot safety / guardrails
# ─────────────────────────────────────────────────────────────

# Columns dropped from any chatbot query result before display or narration.
# Scoped to direct identifiers (HIPAA Safe Harbor style) — quasi-identifiers
# like Gender/Ethnicity are left visible since the dashboard already
# aggregates on them.
SENSITIVE_COLUMNS = [
    "Patient Name",
    "Patient DOB",
    "Patient Address Number",
    "Patient Address Street",
    "Patient Address Full",
    "Patient City",
    "Patient Zip Code",
    "Patient County",
    "Patient State",
    "Patient Country",
    "Patient Latitude",
    "Patient Longitude",
]

PII_MASK_ENABLED = True
CACHE_ENABLED = True

# Estimated pricing only — used for the eval dashboard's cost trend display,
# not billing-accurate. Update to match actual Gemini pricing as needed.
GEMINI_PRICE_PER_1K_INPUT_TOKENS = 0.00125
GEMINI_PRICE_PER_1K_OUTPUT_TOKENS = 0.005