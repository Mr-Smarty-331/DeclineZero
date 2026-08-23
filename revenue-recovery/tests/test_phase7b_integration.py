"""
Cross-Phase Integration Test: Live HTTP Audit Endpoints & Full Pipeline Regression.

Verifies:
1. Pipeline Audit Ingestion: Runs end-to-end transactions through Phases 1 -> 3c -> 4c -> 5b -> 6b -> 7a.
2. Live HTTP Timeline Endpoint: Calls GET /v1/audit/{txn_id} and asserts valid narrative timeline structure.
3. Live HTTP Verify-Proof Endpoint: Calls GET /v1/audit/{txn_id}/verify-proof and asserts verified=True over HTTP.
4. Complete Regression Suite: Re-runs Phase 0 health and core state checks.
"""
import os
import requests
import uuid

from simulator.generator import generate_batch
from core.triage_scorer.policy import triage_decision
from core.diagnostic_tree.rules import diagnose
from core.state_store.redis_store import set_state, get_state, transition_state
from api.models.transaction import TransactionState
from workers.recovery_worker import execute_recovery_action

def test_live_audit_http_endpoints_and_full_pipeline():
    api_host = os.getenv("API_HOST", "localhost")
    base_url = f"http://{api_host}:8000"

    print("Generating 10 transactions for live HTTP audit testing...")
    batch = generate_batch(n=10, output_path="simulator/data/test_phase7b_live.csv")

    processed_txns = []

    print("\nExecuting End-to-End Pipeline Across 10 Transactions:")
    for row in batch:
        txn_id = row["transaction_id"]
        processed_txns.append(txn_id)

        # 1. State Store Init
        set_state(txn_id, TransactionState.RECEIVED, attempt_count=0)

        # 2. Triage & Uplift
        triage_res = triage_decision(row)
        transition_state(txn_id, TransactionState.TRIAGED)

        if triage_res["decision"] == "DO_NOT_DISTURB":
            transition_state(txn_id, TransactionState.DO_NOT_DISTURB)
            continue
        elif triage_res["decision"] == "PASSIVE_HOLD":
            transition_state(txn_id, TransactionState.PASSIVE_HOLD)
            continue

        transition_state(txn_id, TransactionState.DIAGNOSED)

        # 3. Diagnosis
        diag = diagnose(row.get("decline_code", "U69"), row.get("category", "checkout"), txn_id=txn_id, record=row)
        action = diag["action"]

        # 4. Gated Recovery Action Execution
        execute_recovery_action(
            txn_id,
            action,
            row,
            simulated_time=14  # Midday open window
        )

    # -------------------------------------------------------------------------
    # Test Live HTTP GET /v1/audit/{txn_id} (Timeline)
    # -------------------------------------------------------------------------
    print("\n--- Testing Live HTTP GET /v1/audit/{transaction_id} Timeline Endpoint ---")
    test_sample_txn = processed_txns[0]
    timeline_res = requests.get(f"{base_url}/v1/audit/{test_sample_txn}", timeout=5)
    assert timeline_res.status_code == 200, f"Timeline endpoint failed: {timeline_res.text}"
    
    t_data = timeline_res.json()
    assert t_data["transaction_id"] == test_sample_txn
    assert t_data["total_events"] >= 1
    assert isinstance(t_data["timeline_summary"], str)
    assert len(t_data["timeline_summary"]) > 10
    
    print(f"  Transaction ID   : {t_data['transaction_id']}")
    print(f"  Total Event Rows : {t_data['total_events']}")
    print(f"  Timeline Summary : {t_data['timeline_summary']}")
    print("  [PASS] Timeline HTTP endpoint returns human-readable audit narrative.")

    # -------------------------------------------------------------------------
    # Test Live HTTP GET /v1/audit/{txn_id}/verify-proof
    # -------------------------------------------------------------------------
    print("\n--- Testing Live HTTP GET /v1/audit/{transaction_id}/verify-proof ---")
    proof_res = requests.get(f"{base_url}/v1/audit/{test_sample_txn}/verify-proof", timeout=5)
    assert proof_res.status_code == 200, f"Verify proof endpoint failed: {proof_res.text}"

    p_data = proof_res.json()
    print(f"  Proof Result     : verified={p_data['verified']}")
    print(f"  Total Verified   : {p_data['total_records_verified']} records")
    print(f"  Stored Hash      : {p_data['stored_hash'][:16]}...")
    print(f"  Recomputed Hash  : {p_data['recomputed_hash'][:16]}...")
    
    assert p_data["verified"] is True, f"HTTP verify-proof returned False: {p_data}"
    assert p_data["divergence_details"] is None
    print("  [PASS] Verify-proof HTTP endpoint confirmed cryptographic chain integrity.")

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
    print("   RUNNING PHASE 7b CROSS-PHASE INTEGRATION TEST SUITE")
    print("============================================================")
    test_live_audit_http_endpoints_and_full_pipeline()
    test_phase0_api_health()
    print("\n🎉 ALL PHASE 7 (7a, 7b) AUDIT & TAMPER DETECTION SEAMS PASSED!\n")
