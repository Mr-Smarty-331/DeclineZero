"""
Phase 7b Unit Test: Cryptographic Verification Endpoint & Live DBA Tamper Detection.

Validates:
1. Clean Chain Verification: Confirms /verify-proof returns verified=True on an untouched chain.
2. Live DBA-Level Tamper Test: Modifies a row in audit_logs directly via SQL (bypassing log_transition) -> Confirms /verify-proof returns verified=False and pinpoints the diverged transaction and log ID.
3. Inverse Operation Non-Brittleness: Appends a legitimate new transition and confirms normal append operations verify cleanly.
"""
from datetime import datetime, timezone
import uuid

from core.audit_trail.merkle_log import (
    init_audit_db,
    log_transition,
    get_db_connection,
    get_current_chain_hash
)
from api.routes.audit import verify_audit_proof, get_transaction_timeline

async def test_verify_proof_and_tamper_detection():
    print("\n============================================================")
    print("      RUNNING PHASE 7b VERIFY-PROOF & TAMPER TEST SUITE")
    print("============================================================")
    init_audit_db()

    test_txn = f"tamper_demo_{uuid.uuid4().hex[:8]}"

    # Step 1: Append 3 legitimate audit transitions
    print("\n--- Step 1: Appending 3 Legitimate Audit Entries ---")
    log_transition(
        txn_id=test_txn,
        from_state="received",
        to_state="triaged",
        priority_score=0.85,
        cate_score=0.38,
        action_taken="triage_dispatch"
    )
    log_transition(
        txn_id=test_txn,
        from_state="triaged",
        to_state="diagnosed",
        diagnosis_raw={"root_cause": "TIMING_ATTENTION", "rule": "RULE_UPI_U69"},
        action_taken="SEND_FRESH_PAYMENT_LINK_URGENT"
    )
    log_transition(
        txn_id=test_txn,
        from_state="diagnosed",
        to_state="action_sent",
        action_taken="SEND_FRESH_PAYMENT_LINK_URGENT",
        cost_of_action=0.50
    )

    # Step 2: Verify Clean State Proof
    print("\n--- Step 2: Verifying Proof on Clean, Untouched Chain ---")
    proof_clean = await verify_audit_proof(test_txn)
    print(f"  Proof Result: verified={proof_clean.verified} | Verified Records={proof_clean.total_records_verified}")
    print(f"  Stored Tip   : {proof_clean.stored_hash[:16]}...")
    print(f"  Recomputed   : {proof_clean.recomputed_hash[:16]}...")
    assert proof_clean.verified is True, "Clean chain failed cryptographic verification!"
    print("  [PASS] Clean chain mathematically verified from Genesis.")

    # Step 3: DBA-Level Tamper Injection (Direct SQL Update without updating hash chain)
    print("\n--- Step 3: Injecting Direct SQL Tamper (Simulating DBA breach) ---")
    conn = get_db_connection()
    original_action = "SEND_FRESH_PAYMENT_LINK_URGENT"
    tampered_action = "MALICIOUS_TAMPERED_DISPATCH"
    target_row_id = None

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM audit_logs
                WHERE transaction_id = %s AND action_taken = %s
                LIMIT 1;
            """, (test_txn, original_action))
            row = cur.fetchone()
            assert row is not None, "Could not locate target row for tamper injection"
            target_row_id = row[0]

            # Execute unhashed out-of-band edit
            cur.execute("""
                UPDATE audit_logs
                SET action_taken = %s
                WHERE id = %s;
            """, (tampered_action, target_row_id))
        conn.commit()
        print(f"  [TAMPER INJECTED] Modified audit_logs row {target_row_id}: action_taken -> '{tampered_action}'")
    finally:
        conn.close()

    # Step 4: Run /verify-proof to catch the tamper
    print("\n--- Step 4: Re-running /verify-proof against Tampered Ledger ---")
    proof_tampered = await verify_audit_proof(test_txn)
    print(f"  Proof Result: verified={proof_tampered.verified}")
    print(f"  Divergence Details: {proof_tampered.divergence_details}")

    assert proof_tampered.verified is False, "CRITICAL FLAW: Tampered record was not caught by verify-proof!"
    assert proof_tampered.divergence_details is not None, "Missing divergence forensics"
    assert proof_tampered.divergence_details["tampered_transaction_id"] == test_txn
    assert proof_tampered.divergence_details["tampered_log_id"] == str(target_row_id)
    print("  [PASS] Cryptographic verification successfully detected tamper and pinpointed exact row & txn ID!")

    # Step 5: Restore integrity and test normal append non-brittleness
    print("\n--- Step 5: Restoring Ledger & Verifying Non-Brittleness ---")
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE audit_logs
                SET action_taken = %s
                WHERE id = %s;
            """, (original_action, target_row_id))
        conn.commit()
    finally:
        conn.close()

    # Add 1 new legitimate entry
    log_transition(
        txn_id=test_txn,
        from_state="action_sent",
        to_state="resolved_success",
        action_taken="payment_captured"
    )

    proof_restored = await verify_audit_proof(test_txn)
    assert proof_restored.verified is True, "Legitimate new append failed verification"
    print(f"  [PASS] Legitimate transition appended cleanly. Verified: {proof_restored.verified}")

    print("\n🎉 ALL PHASE 7b TAMPER-DETECTION & VERIFY-PROOF TESTS PASSED!\n")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_verify_proof_and_tamper_detection())
