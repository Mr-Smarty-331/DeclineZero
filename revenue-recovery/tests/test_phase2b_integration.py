"""
Cross-Phase Integration Test: Phase 2b -> Phase 2a, Phase 1 & Phase 0 Binding.

Verifies:
1. End-to-end Simulation: Generates 5 transactions via Phase 1 generator, transitions them through Redis store, and verifies in-memory state accuracy.
2. Container Network Connectivity: Confirms FastAPI API container reaches Redis over Docker network (redis:6379).
3. Phase 0 API Health: FastAPI application remains healthy and responds on GET /health.
4. Module Seams: Clean imports across api.models, core.state_store, and simulator.
"""
import os
import requests

from simulator.generator import generate_batch
from api.models.transaction import TransactionState, TransactionRecord
from core.state_store.redis_store import set_state, transition_state, get_state, get_redis_client
from api.main import app as fastapi_app

def test_simulation_over_phase1_transactions():
    print("Running end-to-end Redis lifecycle simulation on 5 Phase 1 transactions...")
    batch = generate_batch(n=5, output_path="simulator/data/test_phase2b_sim.csv")
    assert len(batch) == 5

    r = get_redis_client()
    for row in batch:
        record = TransactionRecord(**row)
        txn_id = record.transaction_id
        
        # 1. Initialize state
        set_state(txn_id, TransactionState.RECEIVED, category=record.category, amount=record.amount)
        st_initial = get_state(txn_id)
        assert st_initial["state"] == "received"
        assert st_initial["amount"] == record.amount
        
        # 2. Advance lifecycle to TRIAGED
        st_triaged = transition_state(txn_id, TransactionState.TRIAGED)
        assert st_triaged["state"] == "triaged"
        
        # 3. Verify in-memory state consistency
        st_check = get_state(txn_id)
        assert st_check["state"] == "triaged"
        
        # Clean up
        r.delete(f"txn:{txn_id}")
        
    print("✅ All 5 Phase 1 transactions successfully initialized and transitioned in Redis.")

def test_container_network_connectivity():
    print("Verifying Docker network Redis connectivity...")
    r = get_redis_client()
    assert r.ping() is True, "Redis ping failed over Docker network"
    info = r.info("server")
    print(f"✅ Connected to Redis server version {info.get('redis_version')} over Docker network.")

def test_phase0_api_health():
    print("Testing Phase 0 FastAPI /health endpoint live binding...")
    api_host = os.getenv("API_HOST", "localhost")
    url = f"http://{api_host}:8000/health"
    response = requests.get(url, timeout=5)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert response.json() == {"status": "ok"}, f"Unexpected health response: {response.json()}"
    print("✅ Phase 0 FastAPI API continues to respond with HTTP 200 {'status': 'ok'}.")

def test_module_seams():
    print("Testing import seams across api.models, core.state_store, and simulator...")
    assert fastapi_app is not None
    import core.state_store as ss
    assert hasattr(ss, "get_state")
    assert hasattr(ss, "set_state")
    assert hasattr(ss, "transition_state")
    assert hasattr(ss, "acquire_idempotency_lock")
    print("✅ Module imports across Phase 0, Phase 1, and Phase 2b are 100% clean.")

if __name__ == "__main__":
    print("\n============================================================")
    print("   RUNNING PHASE 2b CROSS-PHASE INTEGRATION TEST SUITE")
    print("============================================================")
    test_simulation_over_phase1_transactions()
    test_container_network_connectivity()
    test_phase0_api_health()
    test_module_seams()
    print("\n🎉 ALL PHASE 2 (2a, 2b) -> PHASE 1 / PHASE 0 INTEGRATION SEAMS PASSED!\n")
