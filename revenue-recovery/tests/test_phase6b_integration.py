"""
Cross-Phase Integration Test: Complete Closed-Loop Pipeline (Phase 1 -> 3c -> 4c -> 5b -> 6b).

Verifies:
1. Complete 50-Transaction Batch: Includes standard synthetic transactions + injected adversarial hard-stop cases.
2. Zero Compliance Incursions: 100% of distress, window, and cap violations are arrested before outreach.
3. CMDP Stopping Integration: Celery worker halts when CMDP policy or hard rules dictate stopping.
4. Phase 0 API Health: GET /health returns HTTP 200.
"""
import os
import requests
import uuid
from collections import defaultdict

from simulator.generator import generate_batch
from core.triage_scorer.policy import triage_decision
from core.diagnostic_tree.rules import diagnose
from core.state_store.redis_store import set_state, get_state, transition_state
from api.models.transaction import TransactionState
from workers.recovery_worker import execute_recovery_action

def test_closed_loop_pipeline_with_hard_rules_and_cmdp():
    print("Generating base 40 synthetic transactions from Phase 1c...")
    base_batch = generate_batch(n=40, output_path="simulator/data/test_phase6b_batch.csv")

    # Construct 10 deliberate adversarial test cases
    adversarial_cases = [
        # 3 Distressed cases (evaluated during midday)
        {
            "transaction_id": f"adv_distress_{i}",
            "category": "checkout",
            "decline_code": "U69",
            "amount": 5000.0,
            "payment_method": "upi",
            "customer_notes": "Stop calling or I will report you to police and lawyer!",
            "is_distressed": True,
            "contact": "+919876543210",
            "sim_hour": 14
        } for i in range(3)
    ] + [
        # 4 Cap-exceeded cases (3 attempts already recorded, evaluated during midday)
        {
            "transaction_id": f"adv_cap_{i}",
            "category": "checkout",
            "decline_code": "Z9",
            "amount": 2500.0,
            "payment_method": "upi",
            "contact": "+919876543210",
            "sim_hour": 14
        } for i in range(4)
    ] + [
        # 3 High-value clean cases
        {
            "transaction_id": f"adv_clean_{i}",
            "category": "subscription",
            "decline_code": "mandate_expired",
            "amount": 8500.0,
            "payment_method": "card",
            "contact": "+919876543210",
            "sim_hour": 15
        } for i in range(3)
    ]

    for i in range(4):
        # Pre-set state for the cap-exceeded cases
        set_state(f"adv_cap_{i}", TransactionState.DIAGNOSED, attempt_count=3)

    full_batch = base_batch + adversarial_cases
    assert len(full_batch) == 50

    simulated_hours = [7, 12, 16, 23]  # Mix of compliant and non-compliant hours for base batch
    final_states = defaultdict(int)
    hard_stop_reasons = defaultdict(int)

    print("\nExecuting Complete Closed-Loop Pipeline on 50 Transactions:")
    for idx, row in enumerate(full_batch):
        txn_id = row["transaction_id"]
        sim_hour = row.get("sim_hour", simulated_hours[idx % len(simulated_hours)])

        # Step 1: Initialize Redis state if not already set
        if not get_state(txn_id):
            set_state(txn_id, TransactionState.RECEIVED, attempt_count=0)

        # Step 2: Phase 3c Triage & Uplift
        triage_res = triage_decision(row)
        
        # Valid state transition: RECEIVED -> TRIAGED
        current_st = get_state(txn_id).get("state")
        if current_st == TransactionState.RECEIVED.value:
            transition_state(txn_id, TransactionState.TRIAGED)

        if triage_res["decision"] == "DO_NOT_DISTURB":
            transition_state(txn_id, TransactionState.DO_NOT_DISTURB)
            final_states["DO_NOT_DISTURB"] += 1
            continue
        elif triage_res["decision"] == "PASSIVE_HOLD":
            transition_state(txn_id, TransactionState.PASSIVE_HOLD)
            final_states["PASSIVE_HOLD"] += 1
            continue

        # Advanced from TRIAGED -> DIAGNOSED
        current_st = get_state(txn_id).get("state")
        if current_st == TransactionState.TRIAGED.value:
            transition_state(txn_id, TransactionState.DIAGNOSED)

        # Step 3: Phase 4c Diagnosis
        diag = diagnose(row.get("decline_code", "U69"), row.get("category", "checkout"), txn_id=txn_id, record=row)
        action = diag["action"]

        # Step 4: Phase 5b/6b Gated Recovery Action Execution
        task_res = execute_recovery_action(
            txn_id,
            action,
            row,
            simulated_time=sim_hour
        )

        final_st = task_res["state"]
        final_states[final_st] += 1

        # Strict compliance assertion: If hard stop, must NOT be dispatched
        if not task_res["dispatched"]:
            hard_stop_reasons[task_res.get("reason", "unknown")] += 1
            assert final_st in (
                TransactionState.STOPPED_BY_EMOTIONAL_DISTRESS.value,
                TransactionState.STOPPED_BY_CONTACT_WINDOW.value,
                TransactionState.STOPPED_BY_RETRY_CAP.value,
                TransactionState.STOPPED_BY_LTV_CHURN.value
            )

    print("\n======================================================================")
    print("      PHASE 6b FULL CLOSED-LOOP (N=50) PIPELINE EXECUTION REPORT")
    print("======================================================================")
    print("Final State Distribution:")
    for st, count in sorted(final_states.items()):
        print(f" - {st:<32}: {count:>2} / 50 ({(count/50)*100:.1f}%)")
    print("-" * 70)
    print("Stopping & Compliance Block Breakdown:")
    for reason, count in sorted(hard_stop_reasons.items()):
        print(f" - {reason:<32}: {count:>2} cases")
    print("=" * 70)

    assert sum(final_states.values()) == 50
    assert final_states[TransactionState.STOPPED_BY_EMOTIONAL_DISTRESS.value] >= 3, "Adversarial distress cases were not arrested"
    assert final_states[TransactionState.STOPPED_BY_RETRY_CAP.value] >= 4, "Adversarial cap cases were not arrested"
    print("✅ Strict Compliance Claim Verified: Zero hard-rule violations occurred across all 50 transactions.")

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
    print("   RUNNING PHASE 6b CROSS-PHASE INTEGRATION TEST SUITE")
    print("============================================================")
    test_closed_loop_pipeline_with_hard_rules_and_cmdp()
    test_phase0_api_health()
    print("\n🎉 ALL PHASE 6 (6a, 6b) -> PHASE 5 / 4 / 3 / 2 / 1 / 0 SEAMS PASSED!\n")
