"""
Razorpay Webhook Ingestion & Orchestration Layer.

Single live entry point (POST /v1/webhook/razorpay) coordinating:
1. Deduplication Lock (Phase 2b Redis acquire_idempotency_lock)
2. Payment Resolution Short-Circuit (payment.captured -> RESOLVED_SUCCESS)
3. Triage & Causal Uplift Gate (Phase 3c -> DO_NOT_DISTURB / PASSIVE_HOLD / DISPATCH)
4. Diagnostic Root Cause Gate (Phase 4c -> AMBIGUOUS_ESCALATED / Concrete Cause)
5. Regulatory & CMDP Stopping Gate (Phase 6b -> STOPPED_BY_* / Allowed)
6. Asynchronous Recovery Action Dispatch (Phase 5b Celery Worker)
7. Cryptographic Merkle Hash Audit Trail (Phase 7a log_transition)
"""
import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from api.models.transaction import TransactionState, TransactionRecord
from core.state_store.redis_store import acquire_idempotency_lock, set_state, get_state, transition_state
from core.triage_scorer.policy import triage_decision
from core.diagnostic_tree.rules import diagnose
from core.stopping_rules.hard_rules import decide_next_action
from core.audit_trail.merkle_log import log_transition
from workers.recovery_worker import schedule_recovery_action

logger = logging.getLogger("webhook_orchestrator")

webhook_router = APIRouter()


class WebhookPaymentEntity(BaseModel):
    id: str
    amount: int = Field(..., description="Amount in paise (1 INR = 100 paise)")
    currency: str = "INR"
    status: str
    method: Optional[str] = "upi"
    error_code: Optional[str] = None
    error_description: Optional[str] = None
    error_source: Optional[str] = None
    error_step: Optional[str] = None
    error_reason: Optional[str] = None
    email: Optional[str] = None
    contact: Optional[str] = None
    notes: Optional[Dict[str, Any]] = None
    created_at: Optional[int] = None


class WebhookPayloadContainer(BaseModel):
    payment: Optional[Dict[str, Any]] = None
    subscription: Optional[Dict[str, Any]] = None
    invoice: Optional[Dict[str, Any]] = None


class RazorpayWebhookPayload(BaseModel):
    entity: Optional[str] = "event"
    account_id: Optional[str] = "acc_default"
    event: str = Field(..., description="Event type e.g. payment.failed, payment.captured")
    payload: WebhookPayloadContainer
    created_at: Optional[int] = None


class WebhookResponse(BaseModel):
    transaction_id: str
    status: str
    outcome: str
    final_state: str
    action_taken: Optional[str] = None
    reason: Optional[str] = None
    detail: Optional[str] = None


def extract_transaction_details(body: RazorpayWebhookPayload) -> Dict[str, Any]:
    """
    Parses Razorpay nested payload into flattened transaction data dictionary.
    """
    event_type = body.event
    merchant_id = body.account_id or "acc_default"
    
    # Check payment entity first
    p_data = body.payload.payment.get("entity", {}) if body.payload.payment else {}
    s_data = body.payload.subscription.get("entity", {}) if body.payload.subscription else {}
    i_data = body.payload.invoice.get("entity", {}) if body.payload.invoice else {}

    if not p_data and not s_data and not i_data:
        raise HTTPException(
            status_code=400,
            detail="Malformed Razorpay webhook payload: missing payment, subscription, or invoice entity"
        )

    txn_id = p_data.get("id") or s_data.get("id") or i_data.get("id")
    if not txn_id:
        raise HTTPException(
            status_code=400,
            detail="Malformed Razorpay webhook payload: missing transaction/entity ID"
        )
    
    # Infer Category
    if "subscription" in event_type or s_data:
        category = "subscription"
    elif "invoice" in event_type or i_data:
        category = "receivable"
    else:
        category = "checkout"

    # Amount in INR (converted from paise)
    amount_paise = p_data.get("amount") or s_data.get("amount") or i_data.get("amount") or 10000
    amount_inr = float(amount_paise) / 100.0

    payment_method = p_data.get("method") or "upi"
    decline_code = p_data.get("error_code") or (s_data.get("notes", {}).get("reason") if isinstance(s_data.get("notes"), dict) else None) or "U69"
    contact = p_data.get("contact") or "+919876543210"
    email = p_data.get("email") or "customer@example.com"
    notes = p_data.get("notes") or {}
    
    # Customer notes / distress indicators
    customer_notes = str(notes.get("customer_notes", "")) if isinstance(notes, dict) else ""
    is_distressed = notes.get("is_distressed", False) if isinstance(notes, dict) else False

    # Created at / hour of day
    created_at = p_data.get("created_at") or s_data.get("created_at") or i_data.get("created_at") or body.created_at
    if created_at is not None:
        try:
            hour_of_day = int((int(created_at) // 3600) % 24)
        except Exception:
            hour_of_day = 12
    else:
        hour_of_day = 12

    return {
        "transaction_id": txn_id,
        "merchant_id": merchant_id,
        "event_type": event_type,
        "category": category,
        "amount": amount_inr,
        "hour_of_day": hour_of_day,
        "payment_method": payment_method,
        "decline_code": str(decline_code),
        "contact": contact,
        "email": email,
        "customer_notes": customer_notes,
        "is_distressed": is_distressed,
        "hours_since_failure": 0.0,
        "customer_past_success_rate": float(notes.get("customer_past_success_rate", 0.85)) if isinstance(notes, dict) and notes.get("customer_past_success_rate") is not None else 0.85
    }


@webhook_router.post("/razorpay", response_model=WebhookResponse)
async def handle_razorpay_webhook(body: RazorpayWebhookPayload):
    """
    Unified Orchestrator: Ingests Razorpay webhook and executes complete recovery pipeline.
    """
    data = extract_transaction_details(body)
    txn_id = data["transaction_id"]
    event_type = data["event_type"]

    logger.info(f"WEBHOOK_RECEIVED: txn_id={txn_id}, event={event_type}, category={data['category']}, amount=₹{data['amount']:.2f}")

    # ----------------------------------------------------------------------------------
    # Step 1: Idempotency & Deduplication Lock (Phase 2b)
    # ----------------------------------------------------------------------------------
    lock_acquired = acquire_idempotency_lock(
        transaction_id=txn_id,
        merchant_id=data["merchant_id"],
        event_type=event_type
    )
    if not lock_acquired:
        logger.warning(f"IDEMPOTENCY_BLOCKED: Duplicate webhook ignored for txn_id={txn_id}")
        return WebhookResponse(
            transaction_id=txn_id,
            status="duplicate_ignored",
            outcome="DUPLICATE_IGNORED",
            final_state="duplicate_ignored",
            detail="Transaction lock already held or duplicate event processed in last 24h."
        )

    # ----------------------------------------------------------------------------------
    # Step 2: Payment Resolution Event Short-Circuit (Phase 2a / 7a)
    # ----------------------------------------------------------------------------------
    if event_type == "payment.captured":
        logger.info(f"RESOLUTION_EVENT: txn_id={txn_id} captured successfully.")
        curr_blob = get_state(txn_id)
        from_st = curr_blob.get("state") if curr_blob else "received"
        
        # Transition state to terminal RESOLVED_SUCCESS
        set_state(txn_id, TransactionState.RESOLVED_SUCCESS)
        
        # Log to Merkle audit chain
        log_transition(
            txn_id=txn_id,
            from_state=from_st,
            to_state=TransactionState.RESOLVED_SUCCESS.value,
            action_taken="payment_captured",
            cost_of_action=0.0
        )
        
        return WebhookResponse(
            transaction_id=txn_id,
            status="success",
            outcome="RESOLVED_SUCCESS",
            final_state=TransactionState.RESOLVED_SUCCESS.value,
            action_taken="payment_captured"
        )

    # ----------------------------------------------------------------------------------
    # Step 3: Initialize Transaction & State Store (Phase 2a / 2b / 7a)
    # ----------------------------------------------------------------------------------
    existing_blob = get_state(txn_id)
    existing_attempts = int(existing_blob.get("attempt_count", 0)) if existing_blob else 0

    txn_record = TransactionRecord(
        transaction_id=txn_id,
        merchant_id=data["merchant_id"],
        customer_id=f"cust_{txn_id[-6:]}",
        category=data["category"],
        amount=data["amount"],
        hour_of_day=data["hour_of_day"],
        payment_method=data["payment_method"],
        decline_code=data["decline_code"],
        contact=data["contact"],
        email=data["email"],
        customer_notes=data["customer_notes"],
        is_distressed=data["is_distressed"],
        hours_since_failure=data["hours_since_failure"],
        customer_past_success_rate=data["customer_past_success_rate"],
        attempt_count=existing_attempts,
        current_state=TransactionState.RECEIVED
    )

    set_state(
        txn_id,
        TransactionState.RECEIVED,
        category=txn_record.category,
        amount=txn_record.amount,
        payment_method=txn_record.payment_method,
        decline_code=txn_record.decline_code,
        attempt_count=existing_attempts
    )
    
    log_transition(txn_id=txn_id, to_state=TransactionState.RECEIVED.value)
    transition_state(txn_id, TransactionState.TRIAGED)

    # ----------------------------------------------------------------------------------
    # Step 4: Triage & Causal Uplift Scorer (Phase 3c)
    # ----------------------------------------------------------------------------------
    triage_res = triage_decision(txn_record)
    decision = triage_res["decision"]
    p_score = triage_res["priority_score"]
    cate = triage_res["cate_score"]

    if decision == "DO_NOT_DISTURB":
        transition_state(txn_id, TransactionState.DO_NOT_DISTURB)
        log_transition(
            txn_id=txn_id,
            from_state="triaged",
            to_state=TransactionState.DO_NOT_DISTURB.value,
            priority_score=p_score,
            cate_score=cate,
            action_taken="triage_do_not_disturb"
        )
        return WebhookResponse(
            transaction_id=txn_id,
            status="triage_gated",
            outcome="DO_NOT_DISTURB",
            final_state=TransactionState.DO_NOT_DISTURB.value,
            reason="Negative causal uplift (Sleeping dog protected)"
        )

    elif decision == "PASSIVE_HOLD":
        transition_state(txn_id, TransactionState.PASSIVE_HOLD)
        log_transition(
            txn_id=txn_id,
            from_state="triaged",
            to_state=TransactionState.PASSIVE_HOLD.value,
            priority_score=p_score,
            cate_score=cate,
            action_taken="triage_passive_hold"
        )
        return WebhookResponse(
            transaction_id=txn_id,
            status="triage_gated",
            outcome="PASSIVE_HOLD",
            final_state=TransactionState.PASSIVE_HOLD.value,
            reason="High baseline self-resolution probability (2h hold initiated)"
        )

    # DISPATCH path -> Proceed to diagnosis
    transition_state(txn_id, TransactionState.DIAGNOSED)

    # ----------------------------------------------------------------------------------
    # Step 5: Diagnostic Engine & Conformal Fallback (Phase 4c)
    # ----------------------------------------------------------------------------------
    diag_res = diagnose(
        decline_code=txn_record.decline_code,
        category=txn_record.category,
        txn_id=txn_id,
        record=txn_record.model_dump()
    )
    
    root_cause = diag_res["root_cause"]
    action = diag_res["action"]

    # RISK_FLAGGED must be intercepted here — before the CMDP gate — and
    # routed to ESCALATED_HUMAN_REVIEW. These are categorically different from
    # AMBIGUOUS_ESCALATED: we know exactly what this is and it is dangerous.
    # Letting a RISK_FLAGGED transaction reach the action-dispatch path would
    # be a zero-tolerance compliance failure.
    if root_cause == "RISK_FLAGGED":
        transition_state(txn_id, TransactionState.ESCALATED_HUMAN_REVIEW)
        log_transition(
            txn_id=txn_id,
            from_state="diagnosed",
            to_state=TransactionState.ESCALATED_HUMAN_REVIEW.value,
            priority_score=p_score,
            cate_score=cate,
            diagnosis_raw=diag_res,
            action_taken="escalated_human_review_risk_flagged",
            stopping_rule_triggered="RULE_SECURITY_RISK_SHIELD"
        )
        return WebhookResponse(
            transaction_id=txn_id,
            status="risk_flagged_escalated",
            outcome="ESCALATED_HUMAN_REVIEW",
            final_state=TransactionState.ESCALATED_HUMAN_REVIEW.value,
            action_taken="escalated_human_review_risk_flagged",
            reason="RISK_FLAGGED decline code: zero automated outreach — routed to AML/human review"
        )

    if root_cause == "AMBIGUOUS_ESCALATED" or diag_res.get("is_ambiguous"):
        transition_state(txn_id, TransactionState.AMBIGUOUS_ESCALATED)
        log_transition(
            txn_id=txn_id,
            from_state="diagnosed",
            to_state=TransactionState.AMBIGUOUS_ESCALATED.value,
            priority_score=p_score,
            cate_score=cate,
            diagnosis_raw=diag_res,
            action_taken="abstain_ambiguous_escalated"
        )
        return WebhookResponse(
            transaction_id=txn_id,
            status="diagnosed_ambiguous",
            outcome="AMBIGUOUS_ESCALATED",
            final_state=TransactionState.AMBIGUOUS_ESCALATED.value,
            action_taken="abstain",
            reason=f"Conformal set size > 1: {diag_res.get('candidates')}"
        )

    # ----------------------------------------------------------------------------------
    # Step 6: Non-Overridable Hard Rules & CMDP Stopping Gate (Phase 6b)
    # ----------------------------------------------------------------------------------
    gate_decision = decide_next_action(txn_record.model_dump(), current_time=data["hour_of_day"])

    if not gate_decision["allowed"]:
        target_state = gate_decision["state"]
        reason = gate_decision["reason"]
        source = gate_decision["source"]
        
        transition_state(txn_id, target_state)
        log_transition(
            txn_id=txn_id,
            from_state="diagnosed",
            to_state=target_state.value,
            priority_score=p_score,
            cate_score=cate,
            diagnosis_raw=diag_res,
            action_taken="stop",
            stopping_rule_triggered=reason
        )
        return WebhookResponse(
            transaction_id=txn_id,
            status="stopping_gate_blocked",
            outcome="STOPPED",
            final_state=target_state.value,
            action_taken="stop",
            reason=f"{source}: {reason}"
        )

    # ----------------------------------------------------------------------------------
    # Step 7: Asynchronous Action Dispatch (Phase 5b Celery Worker)
    # ----------------------------------------------------------------------------------
    cur_blob = get_state(txn_id)
    cur_att = int(cur_blob.get("attempt_count", 0)) if cur_blob else 0
    set_state(txn_id, TransactionState.ACTION_SENT, attempt_count=cur_att + 1)

    action_cost = 0.50 if action in ("SEND_FRESH_PAYMENT_LINK_URGENT", "SUGGEST_ALTERNATE_METHOD", "SEND_MANDATE_REVIVAL_LINK") else 0.20
    log_transition(
        txn_id=txn_id,
        from_state="diagnosed",
        to_state=TransactionState.ACTION_SENT.value,
        priority_score=p_score,
        cate_score=cate,
        diagnosis_raw=diag_res,
        action_taken=action,
        cost_of_action=action_cost
    )

    schedule_recovery_action(
        txn_id=txn_id,
        action=action,
        transaction_record=txn_record.model_dump(),
        simulated_time=data["hour_of_day"],
        use_salary_alignment=(action == "SCHEDULE_SALARY_ALIGNED_RETRY")
    )

    logger.info(f"DISPATCH_TRIGGERED: txn_id={txn_id}, action={action}, attempt={cur_att + 1}")
    return WebhookResponse(
        transaction_id=txn_id,
        status="action_dispatched",
        outcome="DISPATCHED",
        final_state=TransactionState.ACTION_SENT.value,
        action_taken=action
    )
