"""
Cross-Phase Integration Test: Phase 6a Policy Schema & API System Integrity.

Verifies:
1. JSON Schema & Completeness: stopping_policy.json is valid, loadable JSON with exactly 243 entries covering all state combinations.
2. Zero Missing State Permutations: Every state key (attempts, days, ltv, sentiment) maps to a valid action in ACTIONS.
3. System Stability: Imports and policy loading do not break FastAPI or Docker components.
4. Phase 0 API Health: GET /health returns HTTP 200.
"""
import os
import json
import requests

from policy.mdp_definition import get_all_states, state_to_key, ACTIONS
from policy.value_iteration import POLICY_FILE_PATH, load_stopping_policy

def test_stopping_policy_completeness_and_schema():
    print("Testing stopping_policy.json file existence and completeness...")
    assert POLICY_FILE_PATH.exists(), f"Missing policy file: {POLICY_FILE_PATH}"

    with open(POLICY_FILE_PATH, "r") as f:
        policy_data = json.load(f)

    assert isinstance(policy_data, dict), "Policy must be a JSON object (dict)"
    
    all_states = get_all_states()
    assert len(all_states) == 243, f"Expected 243 discrete states, got {len(all_states)}"
    assert len(policy_data) == 243, f"Expected 243 keys in policy JSON, got {len(policy_data)}"

    # Confirm every single state has a valid action
    action_counts = {a: 0 for a in ACTIONS}
    for s in all_states:
        k = state_to_key(s)
        assert k in policy_data, f"Missing state key in policy: {k}"
        act = policy_data[k]
        assert act in ACTIONS, f"Invalid action '{act}' for state {k}"
        action_counts[act] += 1

    print("\n======================================================================")
    print("         PHASE 6a 243-STATE CMDP OPTIMAL POLICY BREAKDOWN")
    print("======================================================================")
    for act, count in sorted(action_counts.items(), key=lambda x: x[1], reverse=True):
        print(f" - Action: {act:<24} ──► {count:>3} states ({(count/243)*100:.1f}%)")
    print("=" * 70)

    # Confirm loaded via helper
    loaded = load_stopping_policy()
    assert len(loaded) == 243
    print("✅ Stopping policy schema is complete, valid, and fully covers the 243-state discrete MDP space.")

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
    print("   RUNNING PHASE 6a CROSS-PHASE INTEGRATION TEST SUITE")
    print("============================================================")
    test_stopping_policy_completeness_and_schema()
    test_phase0_api_health()
    print("\n🎉 ALL PHASE 6a POLICY INTEGRATION SEAMS PASSED!\n")
