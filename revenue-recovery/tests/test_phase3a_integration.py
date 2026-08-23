"""
Cross-Phase Integration Test: Phase 3a -> Phase 2 & Phase 1 & Phase 0 Binding.

Verifies:
1. Feature Extraction Seam: extract_features works directly on TransactionRecord instances with no field errors.
2. Live HTTP Endpoint: POST /v1/triage returns HTTP 200 with valid priority_score payload over Docker network.
3. State Purity: /v1/triage remains a pure inference endpoint and does not mutate or corrupt Redis state.
4. Phase 0 API Health: GET /health remains HTTP 200.
"""
import os
import requests

from simulator.generator import generate_transaction
from api.models.transaction import TransactionRecord, TransactionState
from core.triage_scorer.features import extract_features
from core.state_store.redis_store import get_state, set_state, get_redis_client
from api.main import app as fastapi_app

def test_feature_extraction_seam():
    print("Testing feature extraction on Phase 2a TransactionRecord...")
    raw_txn = generate_transaction()
    record = TransactionRecord(**raw_txn)
    
    vec = extract_features(record)
    assert vec.shape == (13,), f"Expected 13 features, got shape {vec.shape}"
    assert not any(map(lambda x: x is None, vec))
    print(f"✅ Features extracted successfully (13-dim numerical vector: {vec[:4]}...)")

def test_http_triage_endpoint():
    print("Testing live HTTP POST /v1/triage endpoint...")
    api_host = os.getenv("API_HOST", "localhost")
    url = f"http://{api_host}:8000/v1/triage"

    raw_txn = generate_transaction()
    record = TransactionRecord(**raw_txn)
    payload = record.model_dump()

    response = requests.post(url, json=payload, timeout=5)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    assert "priority_score" in data
    assert 0.0 <= data["priority_score"] <= 1.0
    assert data["transaction_id"] == record.transaction_id
    assert data["category"] == record.category
    print(f"✅ POST /v1/triage returned HTTP 200: priority_score={data['priority_score']} for txn={data['transaction_id']}")

def test_state_purity_during_triage():
    print("Verifying /v1/triage does not mutate Redis state...")
    r = get_redis_client()
    raw_txn = generate_transaction()
    record = TransactionRecord(**raw_txn)
    txn_id = record.transaction_id

    # Initially not present in Redis
    assert get_state(txn_id) is None

    # Call triage endpoint
    api_host = os.getenv("API_HOST", "localhost")
    url = f"http://{api_host}:8000/v1/triage"
    requests.post(url, json=record.model_dump(), timeout=5)

    # Assert still None in Redis (endpoint did not mutate state prematurely)
    assert get_state(txn_id) is None
    print("✅ Triage inference is pure: Redis state remains unmutated (orchestrator in Phase 8 will handle transitions).")

def test_phase0_api_health():
    print("Testing Phase 0 FastAPI /health endpoint live binding...")
    api_host = os.getenv("API_HOST", "localhost")
    url = f"http://{api_host}:8000/health"
    response = requests.get(url, timeout=5)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert response.json() == {"status": "ok"}, f"Unexpected health response: {response.json()}"
    print("✅ Phase 0 FastAPI API continues to respond with HTTP 200 {'status': 'ok'}.")

if __name__ == "__main__":
    print("\n============================================================")
    print("   RUNNING PHASE 3a CROSS-PHASE INTEGRATION TEST SUITE")
    print("============================================================")
    test_feature_extraction_seam()
    test_http_triage_endpoint()
    test_state_purity_during_triage()
    test_phase0_api_health()
    print("\n🎉 ALL PHASE 3a -> PHASE 2 / PHASE 1 / PHASE 0 INTEGRATION SEAMS PASSED!\n")
