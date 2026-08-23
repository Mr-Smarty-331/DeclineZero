"""
Cross-Phase Integration Test: Phase 1b -> Phase 1a & Phase 0 Binding.

Verifies:
1. Backward Compatibility: All Phase 1a fields exist with preserved data types and schemas.
2. Output Path Consistency: Data lands at the expected relative path (simulator/data/synthetic_transactions.csv).
3. Phase 0 API Stability: FastAPI application remains healthy and responds on GET /health.
4. Module Seams: Clean imports across api, core, and simulator packages.
"""
import os
import csv
from pathlib import Path
import requests

from simulator.generator import generate_batch, DEFAULT_OUTPUT_PATH
from api.main import app as fastapi_app

def test_backward_compatibility_with_phase1a():
    print("Testing backward compatibility with Phase 1a schema...")
    batch = generate_batch(n=500)
    assert len(batch) == 500
    
    # Read generated CSV and verify headers
    assert DEFAULT_OUTPUT_PATH.exists()
    with open(DEFAULT_OUTPUT_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        rows = list(reader)
        
    expected_phase1a_fields = [
        "transaction_id", "category", "amount", "hour_of_day", "payment_method", "decline_code"
    ]
    for field in expected_phase1a_fields:
        assert field in headers, f"Phase 1a field '{field}' missing from batch headers!"
        
    expected_phase1b_fields = [
        "is_treated", "actually_resolved", "gt_would_self_resolve", "gt_nudge_effectiveness", "gt_sleeping_dog"
    ]
    for field in expected_phase1b_fields:
        assert field in headers, f"Phase 1b field '{field}' missing from batch headers!"
        
    # Verify field types
    for row in rows[:20]:
        assert len(row["transaction_id"]) > 20
        assert row["category"] in ("checkout", "subscription", "receivable")
        assert float(row["amount"]) > 0
        assert 0 <= int(row["hour_of_day"]) <= 23
        assert row["payment_method"] in ("upi", "card", "netbanking", "upi_mandate", "bank_transfer")
        assert len(row["decline_code"]) > 0
        assert row["is_treated"] in ("True", "False")
        assert row["actually_resolved"] in ("True", "False")
        
    print("✅ All Phase 1a and Phase 1b fields are present, correctly formatted, and backward-compatible.")

def test_phase0_api_health():
    print("Testing Phase 0 FastAPI /health endpoint live binding...")
    api_host = os.getenv("API_HOST", "localhost")
    url = f"http://{api_host}:8000/health"
    response = requests.get(url, timeout=5)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert response.json() == {"status": "ok"}, f"Unexpected health response: {response.json()}"
    print("✅ Phase 0 FastAPI API continues to respond with HTTP 200 {'status': 'ok'}.")

def test_module_seams():
    print("Testing import seams across api, core, and simulator...")
    assert fastapi_app is not None
    import core
    import simulator.decline_codes as dc
    import simulator.generator as gen
    assert len(dc.ALL_VALID_CODES) > 0
    assert hasattr(gen, "generate_transaction")
    assert hasattr(gen, "generate_batch")
    print("✅ Module imports and seam bindings between Phase 0, 1a, and 1b remain 100% clean.")

if __name__ == "__main__":
    print("\n============================================================")
    print("   RUNNING PHASE 1b CROSS-PHASE INTEGRATION TEST SUITE")
    print("============================================================")
    test_backward_compatibility_with_phase1a()
    test_phase0_api_health()
    test_module_seams()
    print("\n🎉 ALL PHASE 1b -> PHASE 1a / PHASE 0 INTEGRATION SEAMS PASSED!\n")
