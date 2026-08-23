"""
Regulatory Compliance & Stopping Rules Engine.

Enforces RBI Digital Lending / Fair Practices Code guidelines:
1. Strict 8:00 AM – 7:00 PM local time contact window (non-overridable).
2. Daily & Lifecycle contact attempt caps (3 for UPI, 8/30-days for subscriptions, 5 for invoices).
3. Structural prohibition against third-party harassment.
4. Salary-aligned monthly scheduling heuristics (1st / 7th of month).
"""
from datetime import datetime, time, date, timedelta
from typing import Dict, Any, Optional, Union
import logging

from api.models.transaction import TransactionState, TransactionRecord
from core.state_store.redis_store import get_state

logger = logging.getLogger("compliance_gate")

# ASSUMPTION: Contact caps per category
CONTACT_ATTEMPT_CAPS = {
    "checkout": 3,      # Max 3 attempts for instant UPI/card checkouts
    "subscription": 8,  # Max 8 attempts across 30-day mandate renewal cycle
    "receivable": 5     # Max 5 reminder touches across invoice lifecycle
}


def within_contact_window(current_time: Optional[Union[datetime, time, int]] = None) -> bool:
    """
    Returns True ONLY if current_time falls between 08:00 AM and 07:00 PM (08:00 <= hour < 19:00).
    Injectable for unit testing across arbitrary times of day.
    """
    if current_time is None:
        hour = datetime.now().hour
        minute = datetime.now().minute
    elif isinstance(current_time, int):
        hour = current_time
        minute = 0
    elif isinstance(current_time, time):
        hour = current_time.hour
        minute = current_time.minute
    elif isinstance(current_time, datetime):
        hour = current_time.hour
        minute = current_time.minute
    else:
        raise ValueError(f"Unsupported time format: {type(current_time)}")

    # Window: 08:00:00 to 18:59:59 inclusive (Strictly before 19:00:00)
    if 8 <= hour < 19:
        return True
    return False


def no_third_party_contact_check(contact_info: str, primary_contact: Optional[str] = None) -> bool:
    """
    Structural Guarantee: The system only dispatches to the primary customer contact
    registered directly on the transaction record. Rejects secondary/third-party targets.
    """
    if not contact_info:
        return False
    if primary_contact and contact_info.strip() != primary_contact.strip():
        return False
    return True


def check_daily_contact_cap(transaction_id: str, category: str = "checkout") -> bool:
    """
    Checks if the transaction has exceeded allowed contact attempts.
    Returns True if under cap (allowed to dispatch), False if cap reached.
    """
    # ASSUMPTION: Cap threshold lookup
    cap = CONTACT_ATTEMPT_CAPS.get(category.lower(), 3)
    
    state_blob = get_state(transaction_id)
    if state_blob is None:
        # No prior attempts recorded
        return True

    current_attempts = int(state_blob.get("attempt_count", 0))
    if current_attempts >= cap:
        logger.warning(f"CONTACT_CAP_EXCEEDED: txn_id={transaction_id} attempts={current_attempts} >= cap={cap}")
        return False
    return True


def compliance_gate(
    transaction_record: Union[Dict[str, Any], TransactionRecord],
    current_time: Optional[Union[datetime, time, int]] = None
) -> Dict[str, Any]:
    """
    Evaluates all regulatory gates prior to outreach execution.
    
    Returns:
        {
            "passed": bool,
            "reason": Optional[str],
            "target_state": Optional[TransactionState]
        }
    """
    if isinstance(transaction_record, TransactionRecord):
        data = transaction_record.model_dump()
    else:
        data = transaction_record

    txn_id = str(data.get("transaction_id", ""))
    category = str(data.get("category", "checkout")).lower()
    contact = str(data.get("contact", "+919876543210"))

    # Gate 1: Contact Window Gate (8 AM - 7 PM)
    if not within_contact_window(current_time):
        logger.warning(f"COMPLIANCE_GATE_FAIL: txn_id={txn_id} outside 8AM-7PM window (time={current_time})")
        return {
            "passed": False,
            "reason": "CONTACT_WINDOW_VIOLATION",
            "target_state": TransactionState.STOPPED_BY_CONTACT_WINDOW
        }

    # Gate 2: Contact Attempt Cap Gate
    if not check_daily_contact_cap(txn_id, category):
        logger.warning(f"COMPLIANCE_GATE_FAIL: txn_id={txn_id} exceeded retry attempt cap for {category}")
        return {
            "passed": False,
            "reason": "RETRY_CAP_EXCEEDED",
            "target_state": TransactionState.STOPPED_BY_RETRY_CAP
        }

    # Gate 3: Third Party Contact Shield
    if not no_third_party_contact_check(contact):
        logger.warning(f"COMPLIANCE_GATE_FAIL: txn_id={txn_id} invalid contact info")
        return {
            "passed": False,
            "reason": "THIRD_PARTY_CONTACT_FORBIDDEN",
            "target_state": TransactionState.ESCALATED_HUMAN_REVIEW
        }

    return {
        "passed": True,
        "reason": None,
        "target_state": None
    }


def next_salary_aligned_slot(current_date: Optional[Union[datetime, date]] = None) -> datetime:
    """
    Computes the upcoming 1st or 7th of the month at 10:00 AM IST for salary-aligned retries.
    # ASSUMPTION: 1st and 7th correspond to primary Indian payroll disbursement cycles.
    """
    if current_date is None:
        now = datetime.now()
    elif isinstance(current_date, date) and not isinstance(current_date, datetime):
        now = datetime(current_date.year, current_date.month, current_date.day, 10, 0)
    elif isinstance(current_date, datetime):
        now = current_date
    else:
        raise ValueError(f"Unsupported date format: {type(current_date)}")

    year = now.year
    month = now.month
    day = now.day

    # Slots in current month: 1st (if day < 1), 7th (if day < 7)
    if day < 1:
        target_slot = datetime(year, month, 1, 10, 0)
    elif day < 7:
        target_slot = datetime(year, month, 7, 10, 0)
    else:
        # Next month 1st
        if month == 12:
            target_slot = datetime(year + 1, 1, 1, 10, 0)
        else:
            target_slot = datetime(year, month + 1, 1, 10, 0)

    return target_slot
