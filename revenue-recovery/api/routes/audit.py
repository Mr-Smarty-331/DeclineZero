"""
Audit Trail API Endpoints.

Provides:
1. GET /v1/audit/{transaction_id} -> Human-readable timeline of state transitions.
2. GET /v1/audit/{transaction_id}/verify-proof -> Cryptographic hash chain verification from Genesis.
"""
import os
import json
import hashlib
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel

from core.audit_trail.merkle_log import (
    get_db_connection,
    get_audit_history,
    get_current_chain_hash,
    compute_leaf,
    GENESIS_HASH
)

audit_router = APIRouter()


class AuditEvent(BaseModel):
    id: str
    transaction_id: str
    from_state: Optional[str] = None
    to_state: str
    priority_score: Optional[float] = None
    cate_score: Optional[float] = None
    action_taken: Optional[str] = None
    stopping_rule_triggered: Optional[str] = None
    cost_of_action: float
    leaf_hash: str
    chain_hash: str
    timestamp: str


class TimelineResponse(BaseModel):
    transaction_id: str
    total_events: int
    timeline_summary: str
    events: List[Dict[str, Any]]


class VerifyProofResponse(BaseModel):
    verified: bool
    transaction_id: str
    recomputed_hash: str
    stored_hash: str
    total_records_verified: int
    divergence_details: Optional[Dict[str, Any]] = None


def format_timeline_summary(events: List[Dict[str, Any]]) -> str:
    """
    Renders chronological event rows into a clean, human-readable narrative string.
    Example: '14:02:01 – Triaged (priority 0.81, cate 0.34). 14:02:02 – Diagnosed: TIMING_ATTENTION (U69)...'
    """
    if not events:
        return "No audit history found for this transaction."

    segments = []
    for ev in events:
        ts = ev.get("timestamp")
        time_str = ts.strftime("%H:%M:%S") if hasattr(ts, "strftime") else str(ts)[:19]
        to_st = ev.get("to_state", "")
        action = ev.get("action_taken")
        stop_rule = ev.get("stopping_rule_triggered")
        cost = float(ev.get("cost_of_action") or 0.0)
        p_score = ev.get("priority_score")
        cate = ev.get("cate_score")
        diag = ev.get("diagnosis_raw")

        if to_st in ("triaged", "passive_hold", "do_not_disturb"):
            p_str = f"priority {p_score:.2f}" if p_score is not None else "priority N/A"
            c_str = f"cate {cate:.2f}" if cate is not None else "cate N/A"
            segments.append(f"{time_str} – Triaged ({p_str}, {c_str}) ──► {to_st}")

        elif to_st in ("diagnosed", "ambiguous_escalated"):
            if isinstance(diag, dict):
                cause = diag.get("root_cause", "UNKNOWN")
                rule = diag.get("decision_path", "")
                segments.append(f"{time_str} – Diagnosed: {cause} (via {rule})")
            else:
                segments.append(f"{time_str} – Diagnosed ──► {to_st}")

        elif to_st == "action_sent":
            cost_str = f"Cost ₹{cost:.2f}" if cost > 0 else "Cost ₹0.00"
            segments.append(f"{time_str} – Action Dispatched: {action} ({cost_str})")

        elif to_st.startswith("stopped_by_"):
            segments.append(f"{time_str} – Stopped by Rule: {stop_rule or to_st} (Zero outreach)")

        elif to_st == "escalated_human_review":
            segments.append(f"{time_str} – Escalated for Human Review (Zero automated contact)")

        else:
            segments.append(f"{time_str} – Transitioned to {to_st}")

    return " ".join(segments)


@audit_router.get("/{transaction_id}", response_model=TimelineResponse)
async def get_transaction_timeline(transaction_id: str = Path(..., description="Transaction Identifier")):
    """
    Returns human-readable timeline and event details for a transaction.
    """
    try:
        events = get_audit_history(transaction_id)
        if not events:
            raise HTTPException(status_code=404, detail=f"No audit logs found for transaction: {transaction_id}")

        summary = format_timeline_summary(events)
        
        # Serialize timestamp objects for json response
        formatted_events = []
        for e in events:
            ev_copy = dict(e)
            if hasattr(ev_copy.get("timestamp"), "isoformat"):
                ev_copy["timestamp"] = ev_copy["timestamp"].isoformat()
            if hasattr(ev_copy.get("id"), "__str__"):
                ev_copy["id"] = str(ev_copy["id"])
            if "cost_of_action" in ev_copy and ev_copy["cost_of_action"] is not None:
                ev_copy["cost_of_action"] = float(ev_copy["cost_of_action"])
            formatted_events.append(ev_copy)

        return TimelineResponse(
            transaction_id=transaction_id,
            total_events=len(events),
            timeline_summary=summary,
            events=formatted_events
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch audit timeline: {str(e)}")


@audit_router.get("/{transaction_id}/verify-proof", response_model=VerifyProofResponse)
async def verify_audit_proof(transaction_id: str = Path(..., description="Transaction Identifier")):
    """
    Cryptographically verifies the entire SHA-256 hash chain from Genesis to tip.
    Pinpoints exact row and transaction where tampering or divergence first occurred.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Fetch all audit logs in chronological insertion order
            cur.execute("""
                SELECT id, transaction_id, from_state, to_state, priority_score, cate_score,
                       diagnosis_raw, action_taken, stopping_rule_triggered, cost_of_action,
                       leaf_hash, chain_hash, timestamp
                FROM audit_logs
                ORDER BY seq_id ASC;
            """)
            rows = cur.fetchall()

            # 2. Fetch stored running chain tip
            stored_tip = get_current_chain_hash()

            if not rows:
                return VerifyProofResponse(
                    verified=True,
                    transaction_id=transaction_id,
                    recomputed_hash=GENESIS_HASH,
                    stored_hash=stored_tip,
                    total_records_verified=0
                )

            # 3. Independently recompute hash chain from Genesis
            recomputed_chain = GENESIS_HASH
            divergence_details = None

            for idx, r in enumerate(rows):
                row_id, r_txn, f_st, t_st, p_score, c_score, diag_raw, act, stop_rule, cost, stored_leaf, stored_chain, ts = r
                
                # Format leaf inputs canonically
                ts_iso = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
                diag_str = json.dumps(diag_raw, sort_keys=True) if diag_raw else "NONE"
                act_str = str(act or "NONE")
                stop_str = str(stop_rule or "NONE")

                # Fresh independent leaf computation
                recalculated_leaf = hashlib.sha256(f"{r_txn}|{ts_iso}|{diag_str}|{act_str}|{stop_str}".encode("utf-8")).hexdigest()
                
                # Chain step: SHA256(prev_chain + leaf)
                recomputed_chain = hashlib.sha256((recomputed_chain + recalculated_leaf).encode("utf-8")).hexdigest()

                # Check for tamper/divergence at this step
                if recomputed_chain != stored_chain or recalculated_leaf != stored_leaf:
                    divergence_details = {
                        "divergence_index": idx,
                        "tampered_log_id": str(row_id),
                        "tampered_transaction_id": r_txn,
                        "stored_leaf_hash": stored_leaf,
                        "recalculated_leaf_hash": recalculated_leaf,
                        "stored_chain_hash": stored_chain,
                        "recomputed_chain_hash": recomputed_chain
                    }
                    break

            is_verified = (divergence_details is None) and (recomputed_chain == stored_tip)

            return VerifyProofResponse(
                verified=is_verified,
                transaction_id=transaction_id,
                recomputed_hash=recomputed_chain,
                stored_hash=stored_tip,
                total_records_verified=len(rows),
                divergence_details=divergence_details
            )
    finally:
        conn.close()
