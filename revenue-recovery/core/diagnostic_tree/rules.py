"""
Deterministic Rule-Based Diagnostic Tree with Conformal Fallback.

1. Procedural expert mapping for verified NPCI/Razorpay decline codes (sub-microsecond execution).
2. Conformal prediction wrapper (α=0.01) for unmapped cooperative bank residuals.
3. Strict regulatory isolation: RISK_FLAGGED codes and conformal multi-candidate sets strictly escalate to human review.
"""
import time
import logging
from typing import Dict, Any, Optional, Union

from api.models.transaction import TransactionRecord
from core.diagnostic_tree.conformal import conformal_diagnose

logger = logging.getLogger("diagnostic_tree")


def diagnose(
    decline_code: str,
    category: str,
    txn_id: Optional[str] = None,
    record: Optional[Union[Dict[str, Any], TransactionRecord]] = None
) -> Dict[str, Any]:
    """
    Diagnoses root causes from decline codes using deterministic rules first,
    falling back cleanly to the conformal prediction layer for unmapped legacy codes.
    """
    t_start = time.perf_counter()

    code_str = str(decline_code).strip()
    cat_str = str(category).strip().lower()

    # 1. Deterministic Rule Tree (Verified NPCI / Razorpay Codes)
    if code_str == "U69":
        root_cause = "TIMING_ATTENTION"
        action = "SEND_FRESH_PAYMENT_LINK_URGENT"
        rule_name = "RULE_UPI_U69_TIMING"
        conformal_info = None

    elif code_str == "Z9":
        root_cause = "INSUFFICIENT_FUNDS"
        action = "SCHEDULE_SALARY_ALIGNED_RETRY"
        rule_name = "RULE_UPI_Z9_FUNDS"
        conformal_info = None

    elif code_str == "U28":
        root_cause = "BANK_TECHNICAL_ISSUE"
        action = "SUGGEST_ALTERNATE_METHOD"
        rule_name = "RULE_UPI_U28_PSP_GLITCH"
        conformal_info = None

    elif code_str in ("U16", "34", "59", "K1", "S1", "S2", "S3"):
        root_cause = "RISK_FLAGGED"
        action = "ESCALATE_HUMAN_REVIEW"
        rule_name = "RULE_SECURITY_RISK_SHIELD"
        conformal_info = None

    elif code_str in ("mandate_expired", "mandate_paused"):
        root_cause = "MANDATE_LAPSED"
        action = "SEND_MANDATE_REVIVAL_LINK"
        rule_name = "RULE_SUBSCRIPTION_MANDATE"
        conformal_info = None

    elif cat_str == "receivable" and code_str in ("overdue_no_dispute", "overdue_with_dispute_flag"):
        root_cause = "OVERDUE_INVOICE"
        action = "SEND_REMINDER_TRACK_PROMISE"
        rule_name = "RULE_RECEIVABLES_OVERDUE"
        conformal_info = None

    else:
        # 2. Phase 4c Conformal Prediction Layer for Ambiguous Residuals
        fallback_record = record or {
            "transaction_id": txn_id or "txn_fallback",
            "decline_code": code_str,
            "category": cat_str,
            "amount": 1000.0,
            "hour_of_day": 12,
            "payment_method": "upi"
        }
        conformal_res = conformal_diagnose(fallback_record, alpha=0.01)
        conformal_info = conformal_res

        if conformal_res["status"] == "SINGLETON":
            root_cause = conformal_res["root_cause"]
            action = conformal_res["action"]
            rule_name = "CONFORMAL_SINGLETON_RESOLVED"
        else:
            root_cause = "AMBIGUOUS_ESCALATED"
            action = "ESCALATE_HUMAN_REVIEW"
            rule_name = "CONFORMAL_ABSTENTION_ESCALATED"

    t_end = time.perf_counter()
    latency_ms = (t_end - t_start) * 1000.0

    decision_result = {
        "root_cause": root_cause,
        "action": action,
        "latency_ms": round(latency_ms, 5),
        "decision_path": rule_name,
        "conformal": conformal_info
    }

    # Structured cryptographic audit logging (Phase 7a)
    try:
        from core.audit_trail.merkle_log import log_transition
        log_transition(
            txn_id=txn_id or "txn_provisional",
            from_state="triaged",
            to_state="diagnosed" if root_cause != "AMBIGUOUS_ESCALATED" else "ambiguous_escalated",
            diagnosis_raw=decision_result,
            action_taken=action,
            stopping_rule_triggered=None
        )
    except Exception as e:
        logger.warning(f"AUDIT_LOG_EXCEPTION: Failed to record audit log: {e}")

    return decision_result
