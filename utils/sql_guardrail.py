"""
SQL safety validator.

Pure function, no I/O: decides whether a piece of SQL text is a single,
read-only SELECT/WITH statement safe to run against the chatbot's
read-only database connection. This is the guardrail that closes the gap
in excel_to_sql.py's execute_query(), which will otherwise commit() any
non-SELECT statement a hallucinated or prompt-injected response returns.
"""

import re
from dataclasses import dataclass

# Security control — deliberately not in config.py, so it can't be casually
# "cleaned up" or shrunk without someone touching this file directly.
_FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "ATTACH", "DETACH", "PRAGMA", "REPLACE", "TRUNCATE",
    "EXEC", "EXECUTE", "VACUUM", "REINDEX", "GRANT", "REVOKE",
]

_ALLOWED_START_RE = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
_FORBIDDEN_RES = [
    (kw, re.compile(rf"\b{kw}\b", re.IGNORECASE)) for kw in _FORBIDDEN_KEYWORDS
]

# Matches a quoted string literal or a comment, so their contents can be
# blanked/removed before keyword and semicolon scanning — this is what
# stops a literal like 'Deleted Patient' or a comment from producing a
# false MULTIPLE_STATEMENTS/FORBIDDEN_KEYWORD verdict.
_STRING_OR_COMMENT_RE = re.compile(
    r"""
    (?P<dstring>"(?:[^"\\]|\\.)*")
    | (?P<sstring>'(?:[^'\\]|\\.)*')
    | (?P<linecomment>--[^\n]*)
    | (?P<blockcomment>/\*.*?\*/)
    """,
    re.VERBOSE | re.DOTALL,
)


@dataclass
class ValidationResult:
    is_valid: bool
    reason: str
    cleaned_sql: str


def _strip_literals_and_comments(sql: str) -> str:
    """Scanning-only text — NOT what gets executed. Literal contents are
    blanked (not removed) so word offsets/boundaries stay stable; comments
    are removed entirely."""

    def _replace(match):
        if match.group("dstring") is not None:
            return '""'
        if match.group("sstring") is not None:
            return "''"
        return " "

    return _STRING_OR_COMMENT_RE.sub(_replace, sql)


def validate_sql(sql: str) -> ValidationResult:
    if not sql or not sql.strip():
        return ValidationResult(False, "EMPTY_QUERY", "")

    original = sql.strip()
    scan_text = _strip_literals_and_comments(original).strip()

    # Trim exactly one optional trailing semicolon before checking for
    # stacked statements — anything left after that is a second statement.
    if scan_text.endswith(";"):
        scan_text = scan_text[:-1].strip()

    if ";" in scan_text:
        return ValidationResult(False, "MULTIPLE_STATEMENTS", "")

    if not _ALLOWED_START_RE.match(scan_text):
        return ValidationResult(False, "NOT_SELECT", "")

    for keyword, pattern in _FORBIDDEN_RES:
        if pattern.search(scan_text):
            return ValidationResult(False, f"FORBIDDEN_KEYWORD:{keyword}", "")

    cleaned_sql = original
    while cleaned_sql.endswith(";"):
        cleaned_sql = cleaned_sql[:-1].strip()

    return ValidationResult(True, "OK", cleaned_sql)
