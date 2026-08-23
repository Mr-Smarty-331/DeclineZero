"""
Phase 5b Unit Test: Contact-Window Compliance Gate & Celery Task Worker.

Validates:
1. Contact Window Gate (8 AM - 7 PM): Injected times (6 AM -> False, 2 PM -> True, 8 PM -> False).
2. Daily Attempt Cap Gate: Blocked when attempts >= cap -> Transitions to STOPPED_BY_RETRY_CAP.
3. Celery Task Execution Outside Window: Blocked at 11 PM -> Transitions to STOPPED_BY_CONTACT_WINDOW.
4. Salary-Aligned Slot Calculation: Computes upcoming 1st or 7th of month.
"""
from datetime import datetime, time
import uuid

from api.models.transaction import TransactionState
from core.state_store.redis_store import set_state, get_state
from core.stopping_rules.compliance import (
    within_contact_window,
    compliance_gate,
    next_salary_aligned_slot,
    check_daily_contact_cap
)
from workers.recovery_worker import execute_recovery_action

def test_contact_window_evaluations():
    print("\n--- Test 1: Evaluating Injectable Contact Window (8 AM - 7 PM) ---")
    
    # 6:00 AM (Early morning -> Disallowed)
    assert within_contact_window(6) is False
    assert within_contact_window(time(6, 30)) is False
    print("  [PASS] 06:00 AM ──► False (Blocked before 8:00 AM)")

    # 2:00 PM (Midday -> Allowed)
    assert within_contact_window(14) is True
    assert within_contact_window(time(14, 0)) is True
    print("  [PASS] 02:00 PM ──► True  (Allowed inside 8AM - 7PM window)")

    # 8:00 PM (Night -> Disallowed)
    assert within_contact_window(20) is False
    assert within_contact_window(time(20, 15)) is False
    print("  [PASS] 08:00 PM ──► False (Blocked after 7:00 PM)")

    # Boundary conditions: 8:00 AM (Allowed), 7:00 PM (Disallowed)
    assert within_contact_window(time(8, 0)) is True
    assert within_contact_window(time(19, 0)) is False
    print("  [PASS] Boundary checks (08:00 -> True, 19:00 -> False)")

def test_daily_attempt_cap_enforcement():
    print("\n--- Test 2: Daily Attempt Cap Enforcement ---")
    txn_id = f"cap_test_{uuid.uuid4().hex[:8]}"
    
    # Set state with attempt_count = 3 (Cap reached for checkout)
    set_state(txn_id, TransactionState.DIAGNOSED, attempt_count=3)
    
    # Check cap check
    allowed = check_daily_contact_cap(txn_id, category="checkout")
    assert allowed is False, "Expected attempt count 3 to exceed checkout cap"

    # Evaluate compliance gate
    record = {
        "transaction_id": txn_id,
        "category": "checkout",
        "amount": 500.0,
        "contact": "+919876543210"
    }
    gate = compliance_gate(record, current_time=14)
    assert gate["passed"] is False
    assert gate["reason"] == "RETRY_CAP_EXCEEDED"
    assert gate["target_state"] == TransactionState.STOPPED_BY_RETRY_CAP
    print("  [PASS] Attempt count 3/3 correctly blocked by RETRY_CAP_EXCEEDED gate.")

def test_celery_task_compliance_transitions():
    print("\n--- Test 3: Celery Task Execution Under Compliance Conditions ---")
    
    # Scenario A: Dispatched outside window (11:00 PM = 23)
    txn_id_night = f"night_{uuid.uuid4().hex[:8]}"
    set_state(txn_id_night, TransactionState.DIAGNOSED, attempt_count=0)
    record_night = {
        "transaction_id": txn_id_night,
        "category": "checkout",
        "amount": 1200.0,
        "contact": "+919876543210"
    }
    res_night = execute_recovery_action(
        txn_id_night,
        "SEND_FRESH_PAYMENT_LINK_URGENT",
        record_night,
        simulated_time=23
    )
    assert res_night["success"] is False
    assert res_night["state"] == TransactionState.STOPPED_BY_CONTACT_WINDOW.value
    assert res_night["dispatched"] is False
    
    state_night = get_state(txn_id_night)
    assert state_night["state"] == TransactionState.STOPPED_BY_CONTACT_WINDOW.value
    print("  [PASS] 11:00 PM Task execution cleanly transitioned state to STOPPED_BY_CONTACT_WINDOW (0 outreach).")

    # Scenario B: Dispatched inside window (2:00 PM = 14)
    txn_id_day = f"day_{uuid.uuid4().hex[:8]}"
    set_state(txn_id_day, TransactionState.DIAGNOSED, attempt_count=0)
    record_day = {
        "transaction_id": txn_id_day,
        "category": "checkout",
        "amount": 1200.0,
        "contact": "+919876543210"
    }
    res_day = execute_recovery_action(
        txn_id_day,
        "SEND_FRESH_PAYMENT_LINK_URGENT",
        record_day,
        simulated_time=14
    )
    assert res_day["success"] is True
    assert res_day["state"] == TransactionState.ACTION_SENT.value
    assert res_day["dispatched"] is True
    
    state_day = get_state(txn_id_day)
    assert state_day["state"] == TransactionState.ACTION_SENT.value
    assert state_day["attempt_count"] == 1
    print("  [PASS] 02:00 PM Task execution cleanly dispatched and transitioned state to ACTION_SENT.")

def test_salary_aligned_slots():
    print("\n--- Test 4: Salary-Aligned Slot Calculation ---")
    
    slot_early = next_salary_aligned_slot(datetime(2026, 8, 3, 12, 0))
    assert slot_early.day == 7
    assert slot_early.month == 8
    print(f"  [PASS] Aug 3 ──► Next slot: {slot_early.strftime('%Y-%m-%d %H:%M')}")

    slot_late = next_salary_aligned_slot(datetime(2026, 8, 15, 12, 0))
    assert slot_late.day == 1
    assert slot_late.month == 9
    print(f"  [PASS] Aug 15 ──► Next slot: {slot_late.strftime('%Y-%m-%d %H:%M')}")

if __name__ == "__main__":
    print("\n============================================================")
    print("           RUNNING PHASE 5b COMPLIANCE UNIT TESTS")
    print("============================================================")
    test_contact_window_evaluations()
    test_daily_attempt_cap_enforcement()
    test_celery_task_compliance_transitions()
    test_salary_aligned_slots()
    print("\n🎉 ALL PHASE 5b COMPLIANCE & CELERY TESTS PASSED!\n")
