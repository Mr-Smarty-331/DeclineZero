"""
Cross-Phase Integration Test: Live Razorpay Webhook Orchestrator, Deduplication & Audit Verification.

Verifies:
1. Live Webhook Duplicate Lock (Phase 2b): Submits duplicate webhook payload over HTTP -> Verifies second call is ignored (status=duplicate_ignored).
2. Live Webhook End-to-End Execution: Submits failed payment -> Triage -> Diagnosis -> CMDP Gate -> Celery Dispatch.
3. Live Merkle Audit Verification (Phase 7a / 7b): Queries GET /v1/audit/{txn_id} timeline and GET /v1/audit/{txn_id}/verify-proof over live HTTP, asserting cryptographic chain integrity.
4. Phase 0 API Health: GET /health returns HTTP 200.
"""
import os
import requests
import uuid
import time

def test_live_webhook_deduplication_and_audit():
    api_host = os.getenv("API_HOST", "localhost")
    base_url = f"http://{api_host}:8000"

    print("\n============================================================")
    print("   RUNNING PHASE 8a LIVE WEBHOOK INTEGRATION TEST SUITE")
    print("============================================================")

    test_txn_id = f"pay_live_test_{uuid.uuid4().hex[:8]}"

    payload = {
        "entity": "event",
        "account_id": "acc_live_demo",
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": test_txn_id,
                    "amount": 99900,  # ₹999.00
                    "currency": "INR",
                    "status": "failed",
                    "method": "upi",
                    "error_code": "U69",
                    "error_description": "UPI collect timed out",
                    "email": "ayush@example.com",
                    "contact": "+919876543210"
                }
            }
        }
    }

    # -------------------------------------------------------------------------
    # Test 1: First Webhook Submission (Should process cleanly)
    # -------------------------------------------------------------------------
    print("\n--- Test 1: Submitting Initial Live Webhook Event ---")
    res_1 = requests.post(f"{base_url}/v1/webhook/razorpay", json=payload, timeout=5)
    assert res_1.status_code == 200, f"Webhook submission failed: {res_1.text}"
    
    data_1 = res_1.json()
    print(f"  First Request Response: status={data_1['status']} | outcome={data_1['outcome']} | final_state={data_1['final_state']}")
    assert data_1["transaction_id"] == test_txn_id
    assert data_1["status"] in ("action_dispatched", "triage_gated", "diagnosed_ambiguous", "stopping_gate_blocked")
    print("  [PASS] Initial webhook event accepted and processed by pipeline.")

    # -------------------------------------------------------------------------
    # Test 2: Second Duplicate Webhook Submission (Should be blocked by 2b Lock)
    # -------------------------------------------------------------------------
    print("\n--- Test 2: Submitting Identical Duplicate Webhook Event ---")
    res_2 = requests.post(f"{base_url}/v1/webhook/razorpay", json=payload, timeout=5)
    assert res_2.status_code == 200, f"Duplicate webhook submission failed: {res_2.text}"

    data_2 = res_2.json()
    print(f"  Duplicate Request Response: status={data_2['status']} | outcome={data_2['outcome']} | detail={data_2.get('detail')}")
    assert data_2["status"] == "duplicate_ignored"
    assert data_2["outcome"] == "DUPLICATE_IGNORED"
    print("  [PASS] Duplicate webhook event successfully blocked by Phase 2b idempotency lock.")

    # -------------------------------------------------------------------------
    # Test 3: Verify Live Merkle Audit Trail for Webhook Event (Phase 7a / 7b)
    # -------------------------------------------------------------------------
    print("\n--- Test 3: Verifying Cryptographic Audit Trail from Live Webhook Traffic ---")
    # Fetch timeline
    timeline_res = requests.get(f"{base_url}/v1/audit/{test_txn_id}", timeout=5)
    assert timeline_res.status_code == 200, f"Audit timeline query failed: {timeline_res.text}"
    t_data = timeline_res.json()
    print(f"  Audit Timeline Summary : {t_data['timeline_summary']}")
    print(f"  Total Audit Events     : {t_data['total_events']}")
    assert t_data["total_events"] >= 1

    # Fetch and verify cryptographic proof
    proof_res = requests.get(f"{base_url}/v1/audit/{test_txn_id}/verify-proof", timeout=5)
    assert proof_res.status_code == 200, f"Audit verify-proof query failed: {proof_res.text}"
    p_data = proof_res.json()
    print(f"  Cryptographic Proof    : verified={p_data['verified']} | Total Verified Records={p_data['total_records_verified']}")
    assert p_data["verified"] is True
    print("  [PASS] Webhook events correctly appended and verified on SHA-256 Merkle hash chain.")

def test_phase0_api_health():
    print("\nTesting Phase 0 FastAPI /health endpoint live binding...")
    api_host = os.getenv("API_HOST", "localhost")
    url = f"http://{api_host}:8000/health"
    response = requests.get(url, timeout=5)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert response.json() == {"status": "ok"}, f"Unexpected health response: {response.json()}"
    print("✅ Phase 0 FastAPI API continues to respond with HTTP 200 {'status': 'ok'}.")

if __name__ == "__main__":
    test_live_webhook_deduplication_and_audit()
    test_phase0_api_health()
    print("\n🎉 ALL PHASE 8a WEBHOOK ORCHESTRATION & INTEGRATION SEAMS PASSED!\n")
