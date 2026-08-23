"""
Phase 6b Unit Test: Hard Rule Short-Circuiting & CMDP Policy Integration.

Validates:
1. Distress Hard Stop Spy: When distress is present, hard rule immediately halts (STOPPED_BY_EMOTIONAL_DISTRESS) and CMDP lookup is NEVER invoked.
2. Contact Window Spy: When outside 8AM-7PM, halts (STOPPED_BY_CONTACT_WINDOW) and CMDP lookup is NEVER invoked.
3. Retry Cap Spy: When attempt cap is exceeded, halts (STOPPED_BY_RETRY_CAP) and CMDP lookup is NEVER invoked.
4. Clean Case Fall-Through: Uninhibited transaction falls through to CMDP lookup and receives valid policy action.
"""
from unittest.mock import patch
import uuid

from api.models.transaction import TransactionState
from core.state_store.redis_store import set_state, get_state
from core.stopping_rules.hard_rules import decide_next_action
import core.stopping_rules.hard_rules as hard_rules_mod

def test_hard_rule_short_circuits():
    print("\n============================================================")
    print("      RUNNING PHASE 6b HARD RULES & SPY UNIT TESTS")
    print("============================================================")

    # -------------------------------------------------------------------------
    # Test 1: Distress Hard Stop Spy (CMDP Lookup MUST NOT be called)
    # -------------------------------------------------------------------------
    print("\n--- Test 1: Customer Emotional Distress Short-Circuit ---")
    distressed_record = {
        "transaction_id": f"distress_{uuid.uuid4().hex[:8]}",
        "category": "checkout",
        "amount": 10000.0,  # High value that would normally get active outreach
        "customer_notes": "Please stop harassing me! I will file a police complaint.",
        "contact": "+919876543210"
    }

    with patch.object(hard_rules_mod, "lookup_policy_action", wraps=hard_rules_mod.lookup_policy_action) as spy_lookup:
        decision_1 = decide_next_action(distressed_record, current_time=14)
        
        assert decision_1["allowed"] is False
        assert decision_1["state"] == TransactionState.STOPPED_BY_EMOTIONAL_DISTRESS
        assert decision_1["source"] == "HARD_RULE_OVERRIDE"
        assert decision_1["reason"] == "CUSTOMER_EMOTIONAL_DISTRESS"
        assert spy_lookup.call_count == 0, "VIOLATION: lookup_policy_action was called despite distress hard stop!"
        print(f"  [PASS] Distress detected ──► STOPPED_BY_EMOTIONAL_DISTRESS | CMDP Spy Call Count: 0 (Strict Short-Circuit)")

    # -------------------------------------------------------------------------
    # Test 2: Contact Window Spy (Outside 8 AM - 7 PM)
    # -------------------------------------------------------------------------
    print("\n--- Test 2: Contact Window Violation Short-Circuit (11:00 PM) ---")
    night_record = {
        "transaction_id": f"night_{uuid.uuid4().hex[:8]}",
        "category": "checkout",
        "amount": 5000.0,
        "contact": "+919876543210"
    }

    with patch.object(hard_rules_mod, "lookup_policy_action", wraps=hard_rules_mod.lookup_policy_action) as spy_lookup:
        decision_2 = decide_next_action(night_record, current_time=23)  # 11 PM
        
        assert decision_2["allowed"] is False
        assert decision_2["state"] == TransactionState.STOPPED_BY_CONTACT_WINDOW
        assert decision_2["source"] == "HARD_RULE_OVERRIDE"
        assert decision_2["reason"] == "CONTACT_WINDOW_VIOLATION"
        assert spy_lookup.call_count == 0, "VIOLATION: lookup_policy_action was called despite contact window violation!"
        print(f"  [PASS] 11:00 PM time ──► STOPPED_BY_CONTACT_WINDOW | CMDP Spy Call Count: 0 (Strict Short-Circuit)")

    # -------------------------------------------------------------------------
    # Test 3: Retry Cap Exceeded Spy
    # -------------------------------------------------------------------------
    print("\n--- Test 3: Attempt Cap Exceeded Short-Circuit (Attempts = 3/3) ---")
    cap_txn_id = f"cap_{uuid.uuid4().hex[:8]}"
    set_state(cap_txn_id, TransactionState.DIAGNOSED, attempt_count=3)
    cap_record = {
        "transaction_id": cap_txn_id,
        "category": "checkout",
        "amount": 2500.0,
        "contact": "+919876543210"
    }

    with patch.object(hard_rules_mod, "lookup_policy_action", wraps=hard_rules_mod.lookup_policy_action) as spy_lookup:
        decision_3 = decide_next_action(cap_record, current_time=14)
        
        assert decision_3["allowed"] is False
        assert decision_3["state"] == TransactionState.STOPPED_BY_RETRY_CAP
        assert decision_3["source"] == "HARD_RULE_OVERRIDE"
        assert decision_3["reason"] == "RETRY_CAP_EXCEEDED"
        assert spy_lookup.call_count == 0, "VIOLATION: lookup_policy_action was called despite retry cap violation!"
        print(f"  [PASS] Attempts 3/3 ──► STOPPED_BY_RETRY_CAP | CMDP Spy Call Count: 0 (Strict Short-Circuit)")

    # -------------------------------------------------------------------------
    # Test 4: Clean Case Fall-Through to CMDP
    # -------------------------------------------------------------------------
    print("\n--- Test 4: Clean Case Fall-Through to CMDP Stopping Policy ---")
    clean_txn_id = f"clean_{uuid.uuid4().hex[:8]}"
    set_state(clean_txn_id, TransactionState.DIAGNOSED, attempt_count=0)
    clean_record = {
        "transaction_id": clean_txn_id,
        "category": "checkout",
        "amount": 7500.0,  # High LTV
        "hours_since_failure": 1.0,  # 0-2 days
        "customer_past_success_rate": 0.95,
        "contact": "+919876543210"
    }

    with patch.object(hard_rules_mod, "lookup_policy_action", wraps=hard_rules_mod.lookup_policy_action) as spy_lookup:
        decision_4 = decide_next_action(clean_record, current_time=14)
        
        assert decision_4["source"] == "CMDP_POLICY"
        assert decision_4["cmdp_state"] is not None
        assert spy_lookup.call_count == 1, "Expected lookup_policy_action to be called exactly once"
        print(f"  [PASS] Clean high-LTV case ──► Action: {decision_4['action']} | State: {decision_4['state']} | CMDP State: {decision_4['cmdp_state']}")

    print("\n🎉 ALL 4 HARD-RULE SPY & CMDP TESTS PASSED WITH STRICT SHORT-CIRCUITING!\n")

if __name__ == "__main__":
    test_hard_rule_short_circuits()
