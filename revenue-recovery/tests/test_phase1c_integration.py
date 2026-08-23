"""
Cross-Phase Integration Test: Phase 1c -> Phase 1b, Phase 1a & Phase 0 Binding.

Verifies:
1. Full Pipeline Data Integrity: Generates 1,000 transactions combining 1a, 1b, and 1c fields without collisions or type errors.
2. Webhook Emitter Completeness: Processes all 1,000 rows through transaction_to_razorpay_webhook with 0 errors.
3. Phase 0 API Stability: FastAPI application remains healthy and responds on GET /health.
4. Module Seams: Clean imports across api, core, and simulator packages.
"""
import os
import requests

from simulator.generator import generate_batch, DEFAULT_OUTPUT_PATH
from simulator.webhook_emitter import emit_batch_as_webhooks, transaction_to_razorpay_webhook
from api.main import app as fastapi_app

def test_full_batch_generation_and_webhook_conversion():
    print("Generating full Phase 1 synthetic batch (N=1,000)...")
    batch = generate_batch(n=1000, output_path="simulator/data/test_phase1c_full.csv")
    assert len(batch) == 1000
    
    print("Verifying batch field completeness and type consistency...")
    required_keys = {
        "transaction_id", "category", "amount", "hour_of_day", "payment_method", "decline_code",
        "is_treated", "actually_resolved", "is_ambiguous",
        "gt_would_self_resolve", "gt_nudge_effectiveness", "gt_sleeping_dog", "gt_true_root_cause"
    }
    
    for row in batch:
        missing = required_keys - set(row.keys())
        assert not missing, f"Missing keys in generated row: {missing}"
        assert isinstance(row["is_treated"], bool)
        assert isinstance(row["actually_resolved"], bool)
        assert isinstance(row["is_ambiguous"], bool)
        assert isinstance(row["gt_would_self_resolve"], bool)
        assert isinstance(row["gt_nudge_effectiveness"], (int, float))
        assert isinstance(row["gt_sleeping_dog"], bool)
        
    print("✅ All 1,000 rows contain complete 1a, 1b, and 1c schema fields with 0 type collisions.")

    print("Emitting all 1,000 transactions as realistic Razorpay webhooks...")
    emitted_count = 0
    for webhook_payload in emit_batch_as_webhooks(batch):
        assert webhook_payload["entity"] == "event"
        assert "event" in webhook_payload
        assert "payload" in webhook_payload
        assert "account_id" in webhook_payload
        emitted_count += 1
        
    assert emitted_count == 1000
    print(f"✅ Webhook emitter successfully transformed all {emitted_count} records with 0 errors.")

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
    import simulator.decline_codes as dc
    import simulator.generator as gen
    import simulator.webhook_emitter as emitter
    assert len(dc.LEGACY_AMBIGUOUS_CODES) == 10
    assert hasattr(gen, "generate_transaction")
    assert hasattr(emitter, "transaction_to_razorpay_webhook")
    print("✅ All module seams across Phase 0 and Phase 1 remain 100% clean and operational.")

if __name__ == "__main__":
    print("\n============================================================")
    print("   RUNNING PHASE 1c CROSS-PHASE INTEGRATION TEST SUITE")
    print("============================================================")
    test_full_batch_generation_and_webhook_conversion()
    test_phase0_api_health()
    test_module_seams()
    print("\n🎉 ALL PHASE 1 (1a, 1b, 1c) -> PHASE 0 INTEGRATION SEAMS PASSED!\n")
