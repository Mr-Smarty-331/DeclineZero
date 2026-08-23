"""
Celery Asynchronous Recovery Action Worker.

Executes outbound recovery actions under strict compliance & CMDP stopping guardrails:
1. Unified Decision Entry Point (decide_next_action): Hard rule short-circuits (Distress, Window, Caps) + CMDP LTV Churn protection.
2. Clean State Machine Transitions (STOPPED_BY_EMOTIONAL_DISTRESS, STOPPED_BY_CONTACT_WINDOW, STOPPED_BY_RETRY_CAP, STOPPED_BY_LTV_CHURN, ACTION_SENT, ESCALATED_HUMAN_REVIEW).
3. Salary-Aligned Retries via apply_async(eta=...).
"""
import os
import logging
from typing import Dict, Any, Optional, Union
from celery import Celery

from api.models.transaction import TransactionState
from core.state_store.redis_store import get_state, set_state, transition_state
from core.stopping_rules.compliance import next_salary_aligned_slot
from core.stopping_rules.hard_rules import decide_next_action
from core.recovery_engine.actions import dispatch_action

logger = logging.getLogger("recovery_worker")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "revenue_recovery_worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
)


@celery_app.task(name="workers.recovery_worker.execute_recovery_action", bind=True)
def execute_recovery_action(
    self,
    txn_id: str,
    action: str,
    transaction_record: Dict[str, Any],
    simulated_time: Optional[Union[int, str]] = None
) -> Dict[str, Any]:
    """
    Executes a recovery action asynchronously.
    Evaluates hard rules and CMDP stopping policy first, updating Redis state accordingly.
    """
    logger.info(f"TASK_START: txn_id={txn_id}, action={action}, simulated_time={simulated_time}")

    # Ensure transaction is tracked in Redis
    current_state_blob = get_state(txn_id)
    if not current_state_blob:
        set_state(txn_id, TransactionState.DIAGNOSED)

    # ----------------------------------------------------------------------------------
    # Step 1: Unified Decision Gate (Hard Rules first, then CMDP Stopping Policy)
    # ----------------------------------------------------------------------------------
    decision = decide_next_action(transaction_record, current_time=simulated_time)
    
    if not decision["allowed"]:
        target_state = decision["state"]
        reason = decision["reason"]
        source = decision["source"]
        logger.warning(f"STOPPING_GATE_BLOCKED: txn_id={txn_id} blocked by {source} ({reason}) -> {target_state}")
        
        # State machine transition to terminal stopped state if not already there
        blob = get_state(txn_id) or {}
        curr_st = blob.get("state")
        if curr_st != target_state.value:
            transition_state(txn_id, target_state)
        
        # Cryptographic Audit Log (Phase 7a)
        try:
            from core.audit_trail.merkle_log import log_transition
            log_transition(
                txn_id=txn_id,
                from_state=curr_st or "diagnosed",
                to_state=target_state.value,
                action_taken="stop",
                stopping_rule_triggered=reason,
                cost_of_action=0.0
            )
        except Exception as e:
            logger.warning(f"AUDIT_LOG_EXCEPTION: Failed to record stopping audit log: {e}")

        return {
            "success": False,
            "dispatched": False,
            "state": target_state.value,
            "reason": reason,
            "source": source,
            "txn_id": txn_id
        }

    # ----------------------------------------------------------------------------------
    # Step 2: Execute Recovery Action Dispatch
    # ----------------------------------------------------------------------------------
    dispatch_res = dispatch_action(action, transaction_record)

    # ----------------------------------------------------------------------------------
    # Step 3: State Machine Transition & Attempt Counter
    # ----------------------------------------------------------------------------------
    if action == "ESCALATE_HUMAN_REVIEW":
        final_state = TransactionState.ESCALATED_HUMAN_REVIEW
        blob = get_state(txn_id) or {}
        if blob.get("state") != final_state.value:
            transition_state(txn_id, final_state)
    else:
        # Increment attempt counter
        blob = get_state(txn_id) or {}
        attempts = int(blob.get("attempt_count", 0)) + 1
        set_state(txn_id, blob.get("state", TransactionState.DIAGNOSED.value), attempt_count=attempts)
        
        final_state = TransactionState.ACTION_SENT
        if blob.get("state") != final_state.value:
            transition_state(txn_id, final_state)

    # Cryptographic Audit Log for Outreach Action (Phase 7a)
    try:
        from core.audit_trail.merkle_log import log_transition
        log_transition(
            txn_id=txn_id,
            from_state="diagnosed",
            to_state=final_state.value,
            action_taken=action,
            stopping_rule_triggered=None,
            cost_of_action=float(dispatch_res.get("cost", 0.0))
        )
    except Exception as e:
        logger.warning(f"AUDIT_LOG_EXCEPTION: Failed to record action dispatch audit log: {e}")

    logger.info(f"TASK_COMPLETE: txn_id={txn_id}, action={action}, final_state={final_state.value}")
    return {
        "success": True,
        "dispatched": True,
        "state": final_state.value,
        "dispatch": dispatch_res,
        "cmdp_state": decision.get("cmdp_state"),
        "txn_id": txn_id
    }


def schedule_recovery_action(
    txn_id: str,
    action: str,
    transaction_record: Dict[str, Any],
    simulated_time: Optional[Union[int, str]] = None,
    use_salary_alignment: bool = False
) -> Any:
    """
    Dispatcher helper: Applies Celery async dispatch with optional salary-aligned ETA.
    """
    if use_salary_alignment and action == "SCHEDULE_SALARY_ALIGNED_RETRY":
        slot_eta = next_salary_aligned_slot()
        logger.info(f"SALARY_ALIGNED_SCHEDULE: txn_id={txn_id} scheduled for {slot_eta.isoformat()}")
        return execute_recovery_action.apply_async(
            args=[txn_id, action, transaction_record, simulated_time],
            eta=slot_eta
        )
    else:
        return execute_recovery_action.delay(txn_id, action, transaction_record, simulated_time)
