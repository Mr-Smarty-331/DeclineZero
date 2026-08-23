"""
Triage Priority & Policy API Endpoint.

Exposes POST /v1/triage:
1. Calculates baseline priority_score and causal uplift cate_score.
2. Applies triage policy routing (DISPATCH | PASSIVE_HOLD | DO_NOT_DISTURB).
3. Transitions state in Redis (RECEIVED -> TRIAGED -> PASSIVE_HOLD/DO_NOT_DISTURB).
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from api.models.transaction import TransactionRecord, TransactionState
from core.triage_scorer.policy import triage_decision
from core.state_store.redis_store import set_state, transition_state, get_state

triage_router = APIRouter(prefix="/v1", tags=["Triage"])


class TriageResponse(BaseModel):
    transaction_id: str
    priority_score: float = Field(..., ge=0.0, le=1.0)
    cate_score: float
    decision: str = Field(..., description="DISPATCH | PASSIVE_HOLD | DO_NOT_DISTURB")
    current_state: str
    category: str
    amount: float


@triage_router.post("/triage", response_model=TriageResponse)
async def triage_transaction(record: TransactionRecord):
    try:
        # 1. Compute triage decision & causal scores
        decision_info = triage_decision(record)
        priority_score = decision_info["priority_score"]
        cate_score = decision_info["cate_score"]
        decision = decision_info["decision"]

        txn_id = record.transaction_id

        # 2. Wire into Redis state machine
        # Initialize record state if not yet registered in Redis
        current_redis_data = get_state(txn_id)
        if current_redis_data is None:
            set_state(
                txn_id,
                TransactionState.RECEIVED,
                category=record.category,
                amount=record.amount,
                payment_method=record.payment_method,
                decline_code=record.decline_code,
                priority_score=priority_score,
                cate_score=cate_score
            )

        # Transition 1: Advance to TRIAGED
        transition_state(txn_id, TransactionState.TRIAGED)
        set_state(txn_id, TransactionState.TRIAGED, priority_score=priority_score, cate_score=cate_score)

        # Transition 2: Policy-directed progression
        if decision == "DO_NOT_DISTURB":
            transition_state(txn_id, TransactionState.DO_NOT_DISTURB)
            final_state = TransactionState.DO_NOT_DISTURB.value
        elif decision == "PASSIVE_HOLD":
            transition_state(txn_id, TransactionState.PASSIVE_HOLD)
            final_state = TransactionState.PASSIVE_HOLD.value
        else:  # DISPATCH
            # Remains at TRIAGED ready for Phase 4 diagnosis
            final_state = TransactionState.TRIAGED.value

        return TriageResponse(
            transaction_id=txn_id,
            priority_score=priority_score,
            cate_score=cate_score,
            decision=decision,
            current_state=final_state,
            category=record.category,
            amount=record.amount
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Triage policy execution failed: {str(e)}")
