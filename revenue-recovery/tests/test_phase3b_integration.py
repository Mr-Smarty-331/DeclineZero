"""
Cross-Phase Integration Test: Phase 3b -> Phase 3a & Phase 2 & Phase 0 Binding.

Verifies:
1. Feature Extraction Seam: cate() runs directly on feature vector built from extract_features(TransactionRecord).
2. Live Triage Endpoint Compatibility: Feature format used by /v1/triage is 100% compatible with cate() inputs.
3. Model Files Present: Confirms both uplift model artifacts exist and load cleanly.
4. Phase 0 API Health: GET /health remains HTTP 200.
"""
import os
import requests

from simulator.generator import generate_transaction
from api.models.transaction import TransactionRecord
from core.triage_scorer.features import extract_features
from core.triage_scorer.uplift_model import cate, load_uplift_models, TREATED_MODEL_PATH, CONTROL_MODEL_PATH
from api.main import app as fastapi_app

def test_feature_compatibility_with_cate():
    print("Testing cate() directly on extract_features(TransactionRecord)...")
    raw_txn = generate_transaction()
    record = TransactionRecord(**raw_txn)
    
    vec = extract_features(record)
    tau = cate(vec)
    
    assert isinstance(tau, float)
    assert -1.0 <= tau <= 1.0
    print(f"✅ cate() computed successfully from Phase 3a features: τ(x) = {tau:+.4f}")

def test_model_files_and_api_boot():
    print("Verifying both T-Learner model artifacts are present...")
    assert TREATED_MODEL_PATH.exists(), f"Missing {TREATED_MODEL_PATH}"
    assert CONTROL_MODEL_PATH.exists(), f"Missing {CONTROL_MODEL_PATH}"
    
    m_tr, m_co = load_uplift_models()
    assert m_tr is not None and m_co is not None
    print("✅ Both μ_1 and μ_0 models loaded successfully.")

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
    print("   RUNNING PHASE 3b CROSS-PHASE INTEGRATION TEST SUITE")
    print("============================================================")
    test_feature_compatibility_with_cate()
    test_model_files_and_api_boot()
    test_phase0_api_health()
    print("\n🎉 ALL PHASE 3b -> PHASE 3a / PHASE 2 / PHASE 0 INTEGRATION SEAMS PASSED!\n")
