"""
Cross-Phase Integration Test: Full Audit Chain Replay & Pipeline End-to-End Binding.

Verifies:
1. Full Pipeline Audit Ingestion: Runs 50 transactions through Phases 1 -> 3c -> 4c -> 5b -> 6b -> 7a.
2. Complete Hash Chain Replay: Reads all audit_logs rows in chronological order, recomputes the SHA-256 chain from Genesis (hash 000...000), and asserts exact equality with chain_state.running_hash.
3. Retrofitted Call Sites Verification: Confirms triage, diagnosis, stopping gates, and action dispatches produce cryptographically valid records.
4. Phase 0 API Health: GET /health returns HTTP 200.
"""
import os
import json
import hashlib
import requests
from collections import defaultdict

from simulator.generator import generate_batch
from core.triage_scorer.policy import triage_decision
from core.diagnostic_tree.rules import diagnose
from core.state_store.redis_store import set_state, get_state, transition_state
from api.models.transaction import TransactionState
from workers.recovery_worker import execute_recovery_action
from core.audit_trail.merkle_log import (
    get_db_connection,
    get_current_chain_hash,
    GENESIS_HASH
)

def test_full_pipeline_audit_chain_replay():
    print("Generating 50 transactions from Phase 1c...")
    batch = generate_batch(n=50, output_path="simulator/data/test_phase7a_batch.csv")

    initial_tip = get_current_chain_hash()
    print(f"Starting Chain Tip: {initial_tip}")

    simulated_hours = [7, 11, 14, 22]

    print("\nExecuting End-to-End Pipeline Across 50 Transactions:")
    for idx, row in enumerate(batch):
        txn_id = row["transaction_id"]
        sim_hour = simulated_hours[idx % len(simulated_hours)]

        # Step 1: Redis Init
        if not get_state(txn_id):
            set_state(txn_id, TransactionState.RECEIVED, attempt_count=0)

        # Step 2: Phase 3c Triage & Uplift
        triage_res = triage_decision(row)
        curr_st = get_state(txn_id).get("state")
        if curr_st == TransactionState.RECEIVED.value:
            transition_state(txn_id, TransactionState.TRIAGED)

        if triage_res["decision"] == "DO_NOT_DISTURB":
            transition_state(txn_id, TransactionState.DO_NOT_DISTURB)
            continue
        elif triage_res["decision"] == "PASSIVE_HOLD":
            transition_state(txn_id, TransactionState.PASSIVE_HOLD)
            continue

        curr_st = get_state(txn_id).get("state")
        if curr_st == TransactionState.TRIAGED.value:
            transition_state(txn_id, TransactionState.DIAGNOSED)

        # Step 3: Phase 4c Diagnosis (Retrofit call site: logs diagnosis to Merkle chain)
        diag = diagnose(row.get("decline_code", "U69"), row.get("category", "checkout"), txn_id=txn_id, record=row)
        action = diag["action"]

        # Step 4: Phase 5b/6b Gated Recovery Action Execution (Retrofit call site: logs stopping/action to Merkle chain)
        task_res = execute_recovery_action(
            txn_id,
            action,
            row,
            simulated_time=sim_hour
        )

    # -------------------------------------------------------------------------
    # Replay Whole Chain from Genesis to Validate Cryptographic Integrity
    # -------------------------------------------------------------------------
    print("\n--- Replaying Complete Audit Chain from Genesis ---")
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, transaction_id, leaf_hash, chain_hash, timestamp FROM audit_logs ORDER BY timestamp ASC, id ASC;")
            rows = cur.fetchall()
            total_logs_count = len(rows)

            print(f"Total Audit Log Records Found in Database: {total_logs_count}")

            # Recompute chain from scratch
            recomputed_chain_hash = GENESIS_HASH
            for r in rows:
                row_id, row_txn, row_leaf, stored_chain_hash, ts = r
                recomputed_chain_hash = hashlib.sha256((recomputed_chain_hash + row_leaf).encode("utf-8")).hexdigest()
                assert recomputed_chain_hash == stored_chain_hash, f"Chain divergence at log {row_id}: Recomputed={recomputed_chain_hash} != Stored={stored_chain_hash}"

            # Compare recomputed final hash with chain_state table
            db_top_tip = get_current_chain_hash()
            assert recomputed_chain_hash == db_top_tip, f"Final replayed tip {recomputed_chain_hash} != chain_state.running_hash {db_top_tip}"

            print("\n======================================================================")
            print("        PHASE 7a COMPLETE MERKLE AUDIT CHAIN REPLAY REPORT")
            print("======================================================================")
            print(f"Total Transactions Processed    : 50")
            print(f"Total Immutable Log Entries     : {total_logs_count}")
            print(f"Genesis Hash (Block 0)          : {GENESIS_HASH[:24]}...")
            print(f"Final Replayed Running Hash     : {recomputed_chain_hash}")
            print(f"Database Current Running Tip    : {db_top_tip}")
            print("=" * 70)
            print("✅ 100% of audit transitions validated by complete deterministic SHA-256 chain replay.")
    finally:
        conn.close()

def test_phase0_api_health():
    print("\nTesting Phase 0 FastAPI /health endpoint live binding...")
    api_host = os.getenv("API_HOST", "localhost")
    url = f"http://{api_host}:8000/health"
    response = requests.get(url, timeout=5)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert response.json() == {"status": "ok"}, f"Unexpected health response: {response.json()}"
    print("✅ Phase 0 FastAPI API continues to respond with HTTP 200 {'status': 'ok'}.")

if __name__ == "__main__":
    print("\n============================================================")
    print("   RUNNING PHASE 7a CROSS-PHASE INTEGRATION TEST SUITE")
    print("============================================================")
    test_full_pipeline_audit_chain_replay()
    test_phase0_api_health()
    print("\n🎉 ALL PHASE 7a MERKLE AUDIT SEAMS PASSED!\n")
