"""
Cross-Phase Integration Test: Phase 5a -> Phase 4 & Phase 0 Binding.

Verifies:
1. Pipeline Integration: Runs diagnose() across 50 sample transactions, feeding the output directly into dispatch_action().
2. Action Matching: Action dispatched matches diagnose() recommendation 100% of the time.
3. Conformal & Risk Isolation: AMBIGUOUS_ESCALATED and RISK_FLAGGED cases strictly route to internal escalation (0 payment links, 0 customer messages).
4. Phase 0 API Health: GET /health returns HTTP 200.
"""
import os
import requests
from simulator.generator import generate_batch
from core.diagnostic_tree.rules import diagnose
from core.recovery_engine.actions import dispatch_action

def test_diagnose_to_dispatch_pipeline():
    print("Generating 50 sample transactions across categories and codes...")
    batch = generate_batch(n=50, output_path="simulator/data/test_phase5a_sim.csv")
    assert len(batch) == 50

    escalation_count = 0
    outreach_count = 0

    print("Running end-to-end diagnosis -> action dispatch pipeline across 50 transactions...")
    for row in batch:
        code = row["decline_code"]
        category = row["category"]
        txn_id = row["transaction_id"]

        # 1. Phase 4 Diagnosis (Rules + Conformal)
        diag = diagnose(code, category, txn_id=txn_id, record=row)
        rec_action = diag["action"]

        # 2. Phase 5 Action Dispatch
        dispatch_res = dispatch_action(rec_action, row)

        assert dispatch_res["action"] == rec_action, f"Action mismatch: expected {rec_action}, got {dispatch_res['action']}"
        assert dispatch_res["success"] is True

        # Check compliance for escalation states
        if diag["root_cause"] in ("RISK_FLAGGED", "AMBIGUOUS_ESCALATED") or rec_action == "ESCALATE_HUMAN_REVIEW":
            escalation_count += 1
            assert dispatch_res["channel"] == "internal_escalation"
            assert dispatch_res["payment_link_id"] is None
            assert dispatch_res["message_sent"] is None
            assert dispatch_res["escalated_for_review"] is True
        else:
            outreach_count += 1
            assert dispatch_res["channel"] in ("whatsapp", "sms")
            assert dispatch_res["payment_link_id"] is not None
            assert dispatch_res["payment_url"] is not None
            assert dispatch_res["message_sent"] is not None

    print(f"\nDispatched 50 transactions successfully:")
    print(f" - Customer Outreach Actions: {outreach_count} cases (Payment links generated)")
    print(f" - Compliance Human Reviews : {escalation_count} cases (Zero outreach, zero links)")
    print("✅ All 50 transactions dispatched cleanly with 100% compliance isolation.")

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
    print("   RUNNING PHASE 5a CROSS-PHASE INTEGRATION TEST SUITE")
    print("============================================================")
    test_diagnose_to_dispatch_pipeline()
    test_phase0_api_health()
    print("\n🎉 ALL PHASE 5a -> PHASE 4 / PHASE 0 INTEGRATION SEAMS PASSED!\n")
