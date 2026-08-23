"""
Deterministic Rule-Based Diagnostic Tree for AI Revenue Recovery.

Sub-millisecond procedural root-cause diagnosis for verified NPCI/Razorpay decline codes.
Contains ZERO heuristic ML/LLM calls to guarantee zero hallucination and strict regulatory compliance.
"""
import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("diagnostic_tree")


def diagnose(decline_code: str, category: str, txn_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Evaluates verified decline codes against deterministic expert rules.
    
    Returns:
        {
            "root_cause": str,
            "action": str,
            "latency_ms": float,
            "decision_path": str
        }
    """
    t_start = time.perf_counter()

    code_str = str(decline_code).strip()
    cat_str = str(category).strip().lower()

    # 1. Unambiguous verified decline codes
    if code_str == "U69":
        root_cause = "TIMING_ATTENTION"
        action = "SEND_FRESH_PAYMENT_LINK_URGENT"
        rule_name = "RULE_UPI_U69_TIMING"

    elif code_str == "Z9":
        root_cause = "INSUFFICIENT_FUNDS"
        action = "SCHEDULE_SALARY_ALIGNED_RETRY"
        rule_name = "RULE_UPI_Z9_FUNDS"

    elif code_str == "U28":
        root_cause = "BANK_TECHNICAL_ISSUE"
        action = "SUGGEST_ALTERNATE_METHOD"
        rule_name = "RULE_UPI_U28_PSP_GLITCH"

    elif code_str in ("U16", "34", "59", "K1", "S1", "S2", "S3"):
        root_cause = "RISK_FLAGGED"
        action = "ESCALATE_HUMAN_REVIEW"
        rule_name = "RULE_SECURITY_RISK_SHIELD"

    elif code_str in ("mandate_expired", "mandate_paused"):
        root_cause = "MANDATE_LAPSED"
        action = "SEND_MANDATE_REVIVAL_LINK"
        rule_name = "RULE_SUBSCRIPTION_MANDATE"

    elif cat_str == "receivable" and code_str in ("overdue_no_dispute", "overdue_with_dispute_flag"):
        root_cause = "OVERDUE_INVOICE"
        action = "SEND_REMINDER_TRACK_PROMISE"
        rule_name = "RULE_RECEIVABLES_OVERDUE"

    else:
        # Fallback for unmapped cooperative-bank strings (ERR-BNK-*) -> Handed off to Phase 4b Conformal Layer
        root_cause = "UNRECOGNIZED"
        action = "SEND_TO_CONFORMAL_CHECK"
        rule_name = "FALLBACK_TO_CONFORMAL"

    t_end = time.perf_counter()
    latency_ms = (t_end - t_start) * 1000.0

    decision_result = {
        "root_cause": root_cause,
        "action": action,
        "latency_ms": round(latency_ms, 5),
        "decision_path": rule_name
    }

    # Structured audit trail logging
    # TODO: replace with Merkle audit in Phase 7
    logger.info(
        "DIAGNOSIS_EVENT",
        extra={
            "txn_id": txn_id,
            "decline_code": code_str,
            "category": cat_str,
            "root_cause": root_cause,
            "action": action,
            "rule": rule_name,
            "latency_ms": latency_ms
        }
    )

    return decision_result
