"""
Transaction State Machine & Core Data Models for AI Revenue Recovery.

Defines:
1. TransactionState: The 14 official lifecycle states.
2. VALID_TRANSITIONS: Explicit state transition graph preventing illegal state jumps.
3. is_valid_transition(): Helper validator for state transitions.
4. TransactionRecord: Core Pydantic model representing in-flight recovery cases.
"""
from enum import Enum
from typing import Optional, Set, Dict
from pydantic import BaseModel, Field


class TransactionState(str, Enum):
    RECEIVED = "received"
    TRIAGED = "triaged"
    PASSIVE_HOLD = "passive_hold"                  # uplift: likely self-resolves, hold 2h
    DIAGNOSED = "diagnosed"
    AMBIGUOUS_ESCALATED = "ambiguous_escalated"     # conformal: >1 plausible cause
    ACTION_SENT = "action_sent"
    RESOLVED_SUCCESS = "resolved_success"           # terminal success
    RESOLVED_FAILED = "resolved_failed"             # terminal, retries exhausted
    ESCALATED_HUMAN_REVIEW = "escalated_human_review"  # risk-flagged, never auto-retried
    STOPPED_BY_RETRY_CAP = "stopped_by_retry_cap"
    STOPPED_BY_CONTACT_WINDOW = "stopped_by_contact_window"
    STOPPED_BY_EMOTIONAL_DISTRESS = "stopped_by_distress"
    STOPPED_BY_LTV_CHURN = "stopped_by_ltv_churn"
    DO_NOT_DISTURB = "do_not_disturb"                # uplift: negative CATE, "sleeping dog"


# Explicit state transition graph defining legal next states
VALID_TRANSITIONS: Dict[TransactionState, Set[TransactionState]] = {
    TransactionState.RECEIVED: {
        TransactionState.TRIAGED
    },
    TransactionState.TRIAGED: {
        TransactionState.PASSIVE_HOLD,
        TransactionState.DIAGNOSED,
        TransactionState.DO_NOT_DISTURB
    },
    TransactionState.PASSIVE_HOLD: {
        TransactionState.RESOLVED_SUCCESS,  # Self-resolved without contact
        TransactionState.DIAGNOSED          # Re-evaluated after 2h if still unpaid
    },
    TransactionState.DIAGNOSED: {
        TransactionState.ACTION_SENT,
        TransactionState.AMBIGUOUS_ESCALATED,
        TransactionState.ESCALATED_HUMAN_REVIEW,
        TransactionState.STOPPED_BY_CONTACT_WINDOW,
        TransactionState.STOPPED_BY_RETRY_CAP,
        TransactionState.STOPPED_BY_EMOTIONAL_DISTRESS,
        TransactionState.STOPPED_BY_LTV_CHURN
    },
    TransactionState.ACTION_SENT: {
        TransactionState.RESOLVED_SUCCESS,
        TransactionState.RESOLVED_FAILED,
        TransactionState.ACTION_SENT,  # Multi-step follow-up retry
        TransactionState.STOPPED_BY_CONTACT_WINDOW,
        TransactionState.STOPPED_BY_RETRY_CAP,
        TransactionState.STOPPED_BY_EMOTIONAL_DISTRESS,
        TransactionState.STOPPED_BY_LTV_CHURN
    },
    TransactionState.STOPPED_BY_CONTACT_WINDOW: {
        TransactionState.ACTION_SENT  # Dispatched once 8 AM window reopens
    },
    # Terminal and escalation states (no automated forward progression)
    TransactionState.RESOLVED_SUCCESS: set(),
    TransactionState.RESOLVED_FAILED: set(),
    TransactionState.ESCALATED_HUMAN_REVIEW: set(),
    TransactionState.AMBIGUOUS_ESCALATED: set(),
    TransactionState.STOPPED_BY_RETRY_CAP: set(),
    TransactionState.STOPPED_BY_EMOTIONAL_DISTRESS: set(),
    TransactionState.STOPPED_BY_LTV_CHURN: set(),
    TransactionState.DO_NOT_DISTURB: set(),
}


def is_valid_transition(from_state: TransactionState, to_state: TransactionState) -> bool:
    """
    Returns True if the transition from `from_state` to `to_state` is legally permitted.
    """
    if from_state not in VALID_TRANSITIONS:
        return False
    return to_state in VALID_TRANSITIONS[from_state]


class TransactionRecord(BaseModel):
    """
    Core data model for an in-flight recovery transaction across the full pipeline.
    """
    # Core attributes from Phase 1 synthetic generator
    transaction_id: str = Field(..., description="Unique transaction UUID")
    category: str = Field(..., description="checkout | subscription | receivable")
    amount: float = Field(..., gt=0, description="Transaction value in INR")
    hour_of_day: int = Field(..., ge=0, le=23, description="Hour of transaction failure (0-23)")
    payment_method: str = Field(..., description="upi | card | netbanking | upi_mandate | bank_transfer")
    decline_code: str = Field(..., description="Verified decline code or legacy ambiguous string")

    # Phase 3a historical merchant telemetry
    customer_past_success_rate: Optional[float] = Field(
        default=0.80, ge=0.0, le=1.0,
        description="Historical customer transaction success rate"
    )

    # Pipeline tracking state
    current_state: TransactionState = Field(
        default=TransactionState.RECEIVED,
        description="Current lifecycle state"
    )
    priority_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Triage recoverability score (0.0 - 1.0)"
    )
    cate_score: Optional[float] = Field(
        default=None,
        description="Estimated Conditional Average Treatment Effect (CATE)"
    )
    attempt_count: int = Field(
        default=0, ge=0,
        description="Number of contact / retry attempts dispatched"
    )

    # Treatment and outcome flags
    is_treated: bool = Field(default=False, description="Whether case received proactive intervention")
    actually_resolved: Optional[bool] = Field(default=None, description="Final resolution outcome")
    is_ambiguous: bool = Field(default=False, description="Whether decline code is an unmapped legacy string")

    # Hidden ground-truth simulation fields (nullable in real production flows)
    gt_would_self_resolve: Optional[bool] = None
    gt_nudge_effectiveness: Optional[float] = None
    gt_sleeping_dog: Optional[bool] = None
    gt_true_root_cause: Optional[str] = None

    class Config:
        use_enum_values = True
