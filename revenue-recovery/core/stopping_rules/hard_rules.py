"""
Non-Overridable Regulatory Hard Rules Layer.

Enforces strict short-circuiting compliance boundaries BEFORE the learned CMDP policy is ever consulted:
1. Customer Emotional Distress -> STOPPED_BY_EMOTIONAL_DISTRESS (Zero outreach, never calls CMDP).
2. Contact Window Violation (outside 8AM-7PM) -> STOPPED_BY_CONTACT_WINDOW.
3. Daily & Lifecycle Retry Cap Exceeded -> STOPPED_BY_RETRY_CAP.
"""
from typing import Dict, Any, Optional, Union
from datetime import datetime, time
import logging

from api.models.transaction import TransactionState, TransactionRecord
from core.stopping_rules.compliance import within_contact_window, check_daily_contact_cap
from core.stopping_rules.cmdp_lookup import get_state_tuple, lookup_policy_action

logger = logging.getLogger("hard_rules")


def detect_customer_distress(transaction_record: Union[Dict[str, Any], TransactionRecord]) -> bool:
    """
    Evaluates customer distress flags and communication text for harassment/distress signals.
    """
    if isinstance(transaction_record, TransactionRecord):
        data = transaction_record.model_dump()
    else:
        data = transaction_record

    if data.get("is_distressed") is True:
        return True

    notes = str(data.get("customer_notes", "")).lower()
    distress_keywords = ["harass", "stop", "lawyer", "complaint", "distress", "police", "fraud", "unauthorized", "threat"]
    return any(kw in notes for kw in distress_keywords)


def check_hard_rules(
    transaction_record: Union[Dict[str, Any], TransactionRecord],
    current_time: Optional[Union[datetime, time, int]] = None
) -> Optional[Dict[str, Any]]:
    """
    Evaluates hard rules in strict priority order, short-circuiting on the first violation.
    Returns a dict describing the hard stop, or None if all hard rules pass.
    """
    if isinstance(transaction_record, TransactionRecord):
        data = transaction_record.model_dump()
    else:
        data = transaction_record

    txn_id = str(data.get("transaction_id", ""))
    category = str(data.get("category", "checkout")).lower()

    # Rule 1: Customer Emotional Distress (Highest Priority Shield)
    if detect_customer_distress(data):
        logger.warning(f"HARD_STOP: txn_id={txn_id} emotional distress detected. Halting outreach immediately.")
        return {
            "hard_stop": True,
            "state": TransactionState.STOPPED_BY_EMOTIONAL_DISTRESS,
            "reason": "CUSTOMER_EMOTIONAL_DISTRESS"
        }

    # Rule 2: RBI Contact Window Violation (8 AM - 7 PM)
    if not within_contact_window(current_time):
        logger.warning(f"HARD_STOP: txn_id={txn_id} outside 8AM-7PM window (time={current_time}).")
        return {
            "hard_stop": True,
            "state": TransactionState.STOPPED_BY_CONTACT_WINDOW,
            "reason": "CONTACT_WINDOW_VIOLATION"
        }

    # Rule 3: Category Contact Attempt Cap Exceeded
    if not check_daily_contact_cap(txn_id, category):
        logger.warning(f"HARD_STOP: txn_id={txn_id} retry attempt cap exceeded for category '{category}'.")
        return {
            "hard_stop": True,
            "state": TransactionState.STOPPED_BY_RETRY_CAP,
            "reason": "RETRY_CAP_EXCEEDED"
        }

    # All hard rules cleared
    return None


def decide_next_action(
    transaction_record: Union[Dict[str, Any], TransactionRecord],
    current_time: Optional[Union[datetime, time, int]] = None
) -> Dict[str, Any]:
    """
    Single unified entry point for stopping & action decisions:
    1. Checks hard rules first. If any hard rule triggers, short-circuits immediately without calling CMDP.
    2. If hard rules clear, resolves the CMDP state tuple and queries stopping_policy.json.
    """
    # 1. Evaluate Non-Overridable Hard Rules
    hard_stop = check_hard_rules(transaction_record, current_time)
    if hard_stop is not None:
        return {
            "allowed": False,
            "action": "stop",
            "state": hard_stop["state"],
            "reason": hard_stop["reason"],
            "source": "HARD_RULE_OVERRIDE",
            "cmdp_state": None
        }

    # 2. Consult Learned CMDP Stopping Policy
    state_tuple = get_state_tuple(transaction_record)
    policy_action = lookup_policy_action(state_tuple)

    if policy_action == "stop":
        logger.info(f"CMDP_STOP: txn_id={transaction_record.get('transaction_id')} stopped by CMDP LTV churn protection at state {state_tuple}")
        return {
            "allowed": False,
            "action": "stop",
            "state": TransactionState.STOPPED_BY_LTV_CHURN,
            "reason": "CMDP_LTV_CHURN_PROTECTION",
            "source": "CMDP_POLICY",
            "cmdp_state": state_tuple
        }
    else:
        return {
            "allowed": True,
            "action": policy_action,
            "state": TransactionState.ACTION_SENT,
            "reason": None,
            "source": "CMDP_POLICY",
            "cmdp_state": state_tuple
        }
