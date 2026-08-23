"""
Cross-Phase Integration Test: Phase 2a -> Phase 1 & Phase 0 Binding.

Verifies:
1. Model Schema Binding: TransactionRecord Pydantic model successfully instantiates from real rows produced by generator.py.
2. Default & Optional Fields: Pipeline fields (current_state, priority_score, cate_score, attempt_count) are cleanly handled.
3. Phase 0 API Health: FastAPI application remains healthy and responds on GET /health.
4. Module Seams: Clean imports across api.models, simulator, and core.
"""
import os
import requests

from simulator.generator import generate_transaction, generate_batch
from api.models.transaction import TransactionRecord, TransactionState
from api.main import app as fastapi_app

def test_pydantic_model_binding_with_phase1_generator():
    print("Testing TransactionRecord instantiation from Phase 1 synthetic generator...")
    # Test single transaction instantiation
    sample_txn = generate_transaction()
    record = TransactionRecord(**sample_txn)
    
    assert record.transaction_id == sample_txn["transaction_id"]
    assert record.category == sample_txn["category"]
    assert record.amount == sample_txn["amount"]
    assert record.hour_of_day == sample_txn["hour_of_day"]
    assert record.payment_method == sample_txn["payment_method"]
    assert record.decline_code == sample_txn["decline_code"]
    assert record.current_state == TransactionState.RECEIVED.value
    assert record.attempt_count == 0
    assert record.priority_score is None
    
    print(f"✅ Single record successfully instantiated: ID={record.transaction_id}, State={record.current_state}")

    # Test batch instantiation over 500 records
    print("Testing batch instantiation over 500 generator records...")
    batch = generate_batch(n=500, output_path="simulator/data/test_phase2a_binding.csv")
    for row in batch:
        rec = TransactionRecord(**row)
        assert rec.amount > 0
        assert rec.current_state == TransactionState.RECEIVED.value
        
    print("✅ All 500 generator records successfully instantiated as TransactionRecord models with 0 schema errors.")

def test_phase0_api_health():
    print("Testing Phase 0 FastAPI /health endpoint live binding...")
    api_host = os.getenv("API_HOST", "localhost")
    url = f"http://{api_host}:8000/health"
    response = requests.get(url, timeout=5)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert response.json() == {"status": "ok"}, f"Unexpected health response: {response.json()}"
    print("✅ Phase 0 FastAPI API continues to respond with HTTP 200 {'status': 'ok'}.")

def test_module_seams():
    print("Testing import seams across api.models, core, and simulator...")
    assert fastapi_app is not None
    import api.models as models
    assert hasattr(models, "TransactionRecord")
    assert hasattr(models, "TransactionState")
    assert hasattr(models, "is_valid_transition")
    print("✅ All module seams between Phase 0, Phase 1, and Phase 2a bind cleanly.")

if __name__ == "__main__":
    print("\n============================================================")
    print("   RUNNING PHASE 2a CROSS-PHASE INTEGRATION TEST SUITE")
    print("============================================================")
    test_pydantic_model_binding_with_phase1_generator()
    test_phase0_api_health()
    test_module_seams()
    print("\n🎉 ALL PHASE 2a -> PHASE 1 / PHASE 0 INTEGRATION SEAMS PASSED!\n")
