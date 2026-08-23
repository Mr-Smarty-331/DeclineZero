"""
Celery Asynchronous Recovery Action Worker.

Executes outbound recovery actions under strict compliance guardrails:
1. Pre-execution Compliance Gate (8AM-7PM window, daily attempt caps, third-party shield).
2. Clean State Transitions (STOPPED_BY_CONTACT_WINDOW, STOPPED_BY_RETRY_CAP, ACTION_SENT, ESCALATED_HUMAN_REVIEW).
3. Salary-Aligned Retries via apply_async(eta=...).
"""
import os
import logging
from typing import Dict, Any, Optional, Union
from celery import Celery

from api.models.transaction import TransactionState
from core.state_store.redis_store import get_state, set_state, transition_state
from core.stopping_rules.compliance import compliance_gate, next_salary_aligned_slot
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
    Evaluates compliance gate first, updating Redis state accordingly.
    """
    logger.info(f"TASK_START: txn_id={txn_id}, action={action}, simulated_time={simulated_time}")

    # Ensure transaction is tracked in Redis
    current_state_blob = get_state(txn_id)
    if not current_state_blob:
        set_state(txn_id, TransactionState.DIAGNOSED)

    # 1. Evaluate Regulatory Compliance Gate
    gate_res = compliance_gate(transaction_record, current_time=simulated_time)
    
    if not gate_res["passed"]:
        target_state = gate_res["target_state"]
        reason = gate_res["reason"]
        logger.warning(f"COMPLIANCE_BLOCKED: txn_id={txn_id} blocked by {reason} -> {target_state}")
        
        # State machine transition to terminal stopped state
        transition_state(txn_id, target_state)
        
        return {
            "success": False,
            "dispatched": False,
            "state": target_state.value,
            "reason": reason,
            "txn_id": txn_id
        }

    # 2. Execute Recovery Action Dispatch
    dispatch_res = dispatch_action(action, transaction_record)

    # 3. State Machine Transition & Attempt Counter
    if action == "ESCALATE_HUMAN_REVIEW":
        final_state = TransactionState.ESCALATED_HUMAN_REVIEW
        transition_state(txn_id, final_state)
    else:
        # Increment attempt counter
        blob = get_state(txn_id) or {}
        attempts = int(blob.get("attempt_count", 0)) + 1
        set_state(txn_id, blob.get("state", TransactionState.DIAGNOSED.value), attempt_count=attempts)
        
        final_state = TransactionState.ACTION_SENT
        transition_state(txn_id, final_state)

    logger.info(f"TASK_COMPLETE: txn_id={txn_id}, action={action}, final_state={final_state.value}")
    return {
        "success": True,
        "dispatched": True,
        "state": final_state.value,
        "dispatch": dispatch_res,
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
