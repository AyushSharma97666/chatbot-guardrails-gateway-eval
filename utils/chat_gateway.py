"""
The single chokepoint for the chatbot pipeline.

Nothing should reach Gemini or HealthcareDB.db from the UI except through
ask_question(). It wires together, in order: cache lookup -> SQL
generation -> validation -> read-only execution -> PII masking ->
narration (cached or fresh) -> groundedness check -> audit logging.
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config
from utils.logger import get_logger
from utils import sql_guardrail, readonly_db, pii_guard, groundedness, audit_log, query_cache
from utils.gemini_utils import get_gemini_response, extract_sql_from_response, generate_chatbot_response

logger = get_logger("chat_gateway")

# Deliberately generic — never echoes the validator's internal reason back to
# the user, so a would-be attacker can't use error text to iterate toward a
# bypass.
_REFUSAL_MESSAGE = (
    "I can only run safe, read-only queries against this database, and that "
    "request couldn't be completed that way. Try rephrasing your question."
)


def _estimate_cost(prompt_tokens, completion_tokens):
    if prompt_tokens is None and completion_tokens is None:
        return None
    input_cost = (prompt_tokens or 0) / 1000 * getattr(config, "GEMINI_PRICE_PER_1K_INPUT_TOKENS", 0)
    output_cost = (completion_tokens or 0) / 1000 * getattr(config, "GEMINI_PRICE_PER_1K_OUTPUT_TOKENS", 0)
    return round(input_cost + output_cost, 6)


def _blocked_result(question, normalized, reason, start_time, source, detail=None, generated_sql=None):
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    audit_id = audit_log.log_event(
        question=question, normalized_question=normalized, generated_sql=generated_sql,
        validator_verdict="BLOCK", validator_reason=reason,
        executed=0, cache_hit=0, latency_ms=latency_ms, source=source,
        error=detail,
    )
    return {
        "success": False, "blocked": True, "block_reason": reason,
        "sql": None, "df": None, "masked_columns": [], "row_count": 0,
        "narration": _REFUSAL_MESSAGE, "narration_source": None,
        "groundedness_ok": None, "cache_hit": False,
        "latency_ms": latency_ms, "audit_log_id": audit_id, "error": detail or reason,
    }


def ask_question(user_input: str, source: str = "chat_ui", bypass_cache: bool = False) -> dict:
    start_time = time.perf_counter()
    normalized = query_cache.normalize_question(user_input)
    cache_enabled = getattr(config, "CACHE_ENABLED", True) and not bypass_cache

    cache_entry = None
    cache_hit = False
    sql = None
    prompt_tokens = None
    completion_tokens = None

    if cache_enabled:
        candidate = query_cache.lookup(user_input)
        if candidate:
            # Defense in depth: re-validate even a cached row before trusting it.
            revalidation = sql_guardrail.validate_sql(candidate["validated_sql"])
            if revalidation.is_valid:
                sql = revalidation.cleaned_sql
                cache_entry = candidate
                cache_hit = True
                logger.info(f"Cache hit for question: {user_input[:80]}")
            else:
                logger.warning(f"Cached SQL failed re-validation ({revalidation.reason}), treating as cache miss")

    if sql is None:
        sql_response = get_gemini_response(user_input=user_input, prompt_name="sql_generator", temperature=0.3)
        usage = sql_response.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")

        if not sql_response.get("success"):
            return _blocked_result(
                user_input, normalized, "GENERATION_FAILED", start_time, source,
                detail=sql_response.get("error"),
            )

        extracted = extract_sql_from_response(sql_response.get("text") or "")
        if not extracted:
            return _blocked_result(user_input, normalized, "NO_SQL_EXTRACTED", start_time, source)

        validation = sql_guardrail.validate_sql(extracted)
        if not validation.is_valid:
            logger.warning(f"Blocked generated SQL ({validation.reason}): {extracted[:200]}")
            return _blocked_result(
                user_input, normalized, validation.reason, start_time, source,
                generated_sql=extracted,
            )

        sql = validation.cleaned_sql

    # Always execute fresh against the live DB, cache hit or not — the cache
    # reuses SQL text, never stale result rows.
    exec_result = readonly_db.execute_readonly_query(sql)
    if not exec_result["success"]:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        audit_id = audit_log.log_event(
            question=user_input, normalized_question=normalized, generated_sql=sql,
            validator_verdict="ALLOW", validator_reason="OK", executed=0,
            cache_hit=int(cache_hit), latency_ms=latency_ms, source=source,
            error=exec_result["error"], prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        )
        return {
            "success": False, "blocked": False, "block_reason": None, "sql": sql,
            "df": None, "masked_columns": [], "row_count": 0,
            "narration": "That query couldn't be run. Try rephrasing your question.",
            "narration_source": None, "groundedness_ok": None, "cache_hit": cache_hit,
            "latency_ms": latency_ms, "audit_log_id": audit_id, "error": exec_result["error"],
        }

    df = exec_result["df"]
    row_count = exec_result["row_count"]
    masked_df, masked_columns = pii_guard.mask_dataframe(df)

    # Cache writes only for real chat traffic — eval runs pass bypass_cache=True
    # and must never pollute the real-usage cache with synthetic questions.
    if source == "chat_ui" and cache_enabled:
        if cache_entry is None:
            cache_entry = query_cache.store(user_input, sql, source="auto")
        else:
            query_cache.touch_hit(cache_entry["id"])

    if cache_hit and cache_entry and query_cache.is_narration_fresh(cache_entry):
        narration = cache_entry["last_narration"]
        narration_source = "cached"
    else:
        result_dict = {
            "success": True,
            "data": masked_df.values.tolist(),
            "columns": list(masked_df.columns),
            "row_count": row_count,
        }
        narration_response = generate_chatbot_response(user_input=user_input, query_result=result_dict)
        narration_usage = narration_response.get("usage") or {}
        prompt_tokens = (prompt_tokens or 0) + (narration_usage.get("prompt_tokens") or 0) or prompt_tokens
        completion_tokens = (completion_tokens or 0) + (narration_usage.get("completion_tokens") or 0) or completion_tokens

        narration = narration_response.get("text") or "Here are the results above."
        if not narration_response.get("success"):
            narration = "Here are the results above."
        narration_source = "generated"

        if source == "chat_ui" and cache_enabled and cache_entry:
            query_cache.update_narration(cache_entry["id"], narration)

    groundedness_ok, _unmatched = groundedness.check_groundedness(narration, masked_df, row_count)

    latency_ms = int((time.perf_counter() - start_time) * 1000)
    audit_id = audit_log.log_event(
        question=user_input, normalized_question=normalized, generated_sql=sql,
        validator_verdict="ALLOW", validator_reason="OK", executed=1, row_count=row_count,
        masked_columns=",".join(masked_columns) if masked_columns else None,
        groundedness_ok=int(groundedness_ok), cache_hit=int(cache_hit),
        narration_cache_hit=int(narration_source == "cached"),
        latency_ms=latency_ms, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        estimated_cost_usd=_estimate_cost(prompt_tokens, completion_tokens), source=source,
    )

    return {
        "success": True, "blocked": False, "block_reason": None, "sql": sql,
        "df": masked_df, "masked_columns": masked_columns, "row_count": row_count,
        "narration": narration, "narration_source": narration_source,
        "groundedness_ok": groundedness_ok, "cache_hit": cache_hit,
        "latency_ms": latency_ms, "audit_log_id": audit_id, "error": None,
    }
