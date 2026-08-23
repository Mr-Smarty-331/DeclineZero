"""
CMDP Runtime State Tuple Resolver and Policy Lookup.

Extracts discretized MDP state coordinates from a live transaction:
- attempts_remaining ∈ {0, 1, ..., 8}
- days_since_failure ∈ {"0-2", "3-7", "8-30"}
- ltv_tier           ∈ {"low", "medium", "high"}
- sentiment          ∈ {"neutral", "negative", "distressed"}

Looks up optimal action in policy/stopping_policy.json without silent defaults.
"""
from typing import Dict, Any, Tuple, Union, Optional
from datetime import datetime

from api.models.transaction import TransactionRecord
from core.state_store.redis_store import get_state
from policy.mdp_definition import state_to_key
from policy.value_iteration import load_stopping_policy

_cached_policy: Optional[Dict[str, str]] = None


def get_state_tuple(
    transaction_record: Union[Dict[str, Any], TransactionRecord]
) -> Tuple[int, str, str, str]:
    """
    Extracts the 4-tuple discrete state coordinate from transaction metadata:
    (attempts_remaining, days_since_failure, ltv_tier, sentiment)
    """
    if isinstance(transaction_record, TransactionRecord):
        data = transaction_record.model_dump()
    else:
        data = transaction_record

    txn_id = str(data.get("transaction_id", ""))
    amount = float(data.get("amount", 100.0))
    past_success = float(data.get("customer_past_success_rate", 0.80))
    hours_since_failure = float(data.get("hours_since_failure", 0.0))

    # 1. Attempts remaining (derived from Phase 2b Redis state, capped at 8 max)
    state_blob = get_state(txn_id)
    attempt_count = int(state_blob.get("attempt_count", 0)) if state_blob else 0
    attempts_remaining = max(0, min(8, 8 - attempt_count))

    # 2. Days since failure
    # If hours_since_failure is available, use it; otherwise fallback to days_since_failure if present
    if "hours_since_failure" in data:
        days = hours_since_failure / 24.0
    else:
        days = float(data.get("days_since_failure_num", 0.0))

    if days <= 2.0:
        days_tier = "0-2"
    elif days <= 7.0:
        days_tier = "3-7"
    else:
        days_tier = "8-30"

    # 3. LTV Tier (# ASSUMPTION: calculated from amount and past transaction history)
    # High: Amount >= 5000 or past success >= 0.85 with amount >= 2500
    # Medium: Amount >= 1500
    # Low: Amount < 1500
    if amount >= 5000.0 or (past_success >= 0.85 and amount >= 2500.0):
        ltv_tier = "high"
    elif amount >= 1500.0:
        ltv_tier = "medium"
    else:
        ltv_tier = "low"

    # 4. Customer Sentiment (# ASSUMPTION: keyword-based sentiment extraction stub)
    notes = str(data.get("customer_notes", "")).lower()
    distress_keywords = ["harass", "stop", "lawyer", "complaint", "distress", "police", "fraud", "unauthorized", "threat"]
    negative_keywords = ["bad", "slow", "error", "annoyed", "fail", "broken", "glitch", "cancel"]

    if data.get("is_distressed") or any(kw in notes for kw in distress_keywords):
        sentiment = "distressed"
    elif data.get("is_negative") or any(kw in notes for kw in negative_keywords):
        sentiment = "negative"
    else:
        sentiment = "neutral"

    return (attempts_remaining, days_tier, ltv_tier, sentiment)


def lookup_policy_action(state_tuple: Tuple[int, str, str, str]) -> str:
    """
    Looks up the optimal action from stopping_policy.json.
    Raises KeyError if the state tuple is not found (Zero silent defaults).
    """
    global _cached_policy
    if _cached_policy is None:
        _cached_policy = load_stopping_policy()

    key = state_to_key(state_tuple)
    if key not in _cached_policy:
        raise KeyError(f"CRITICAL ERROR: State tuple {state_tuple} (key '{key}') missing from CMDP stopping policy!")

    return _cached_policy[key]
