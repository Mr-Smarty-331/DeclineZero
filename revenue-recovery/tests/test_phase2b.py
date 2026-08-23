"""
Phase 2b Unit Test: Redis State Management & Idempotency Locking.

Tests:
1. transition_state succeeds on legal transition and raises on illegal jump.
2. acquire_idempotency_lock returns True on initial call and False on duplicate webhook.
3. Different event_type values for the same transaction_id operate under independent locks.
"""
import uuid
from api.models.transaction import TransactionState
from core.state_store.redis_store import (
    get_state,
    set_state,
    transition_state,
    acquire_idempotency_lock,
    get_redis_client
)

def test_redis_state_and_idempotency():
    r = get_redis_client()
    assert r.ping() is True, "Redis container unreachable"

    test_txn_id = f"test_txn_{uuid.uuid4().hex[:10]}"
    test_merchant_id = "acc_merchant_demo_99"

    print(f"\n--- Running Phase 2b Unit Tests on Redis (txn_id={test_txn_id}) ---")

    # ----------------------------------------------------------------------------------
    # TEST 1: State Management & Transition Enforcement
    # ----------------------------------------------------------------------------------
    print("\n1. Testing state initialization & transitions:")
    initial_state = set_state(test_txn_id, TransactionState.RECEIVED, category="checkout", amount=1299.0)
    assert initial_state["state"] == "received"
    print(f"  [PASS] Initial state saved: {get_state(test_txn_id)}")

    # Valid transition: RECEIVED -> TRIAGED
    updated = transition_state(test_txn_id, TransactionState.TRIAGED)
    assert updated["state"] == "triaged"
    print(f"  [PASS] Legal transition (RECEIVED -> TRIAGED) accepted: state={updated['state']}")

    # Illegal transition: TRIAGED -> RESOLVED_SUCCESS (Must raise ValueError)
    try:
        transition_state(test_txn_id, TransactionState.RESOLVED_SUCCESS)
        assert False, "Failed: Illegal transition TRIAGED -> RESOLVED_SUCCESS was not blocked!"
    except ValueError as e:
        print(f"  [PASS] Illegal jump (TRIAGED -> RESOLVED_SUCCESS) correctly blocked with error:\n         '{e}'")

    # ----------------------------------------------------------------------------------
    # TEST 2: Duplicate Webhook Idempotency Lock
    # ----------------------------------------------------------------------------------
    print("\n2. Testing duplicate webhook idempotency deduplication:")
    first_attempt = acquire_idempotency_lock(test_txn_id, test_merchant_id, "payment.failed")
    assert first_attempt is True, "First lock acquisition failed!"
    print(f"  [PASS] First webhook arrival (payment.failed): Lock Acquired = {first_attempt} (Proceed)")

    second_attempt = acquire_idempotency_lock(test_txn_id, test_merchant_id, "payment.failed")
    assert second_attempt is False, "Duplicate lock was incorrectly granted!"
    print(f"  [PASS] Duplicate webhook arrival (payment.failed): Lock Acquired = {second_attempt} (Correctly Dropped)")

    # ----------------------------------------------------------------------------------
    # TEST 3: Distinct Event Types for the Same Transaction
    # ----------------------------------------------------------------------------------
    print("\n3. Testing distinct event types for same transaction:")
    resolution_event = acquire_idempotency_lock(test_txn_id, test_merchant_id, "payment.captured")
    assert resolution_event is True, "Independent event type payment.captured was incorrectly blocked!"
    print(f"  [PASS] Distinct resolution event (payment.captured): Lock Acquired = {resolution_event} (Allowed independently)")

    # Clean up test keys
    r.delete(f"txn:{test_txn_id}")
    r.delete(f"idemp:{test_merchant_id}:{test_txn_id}:payment.failed")
    r.delete(f"idemp:{test_merchant_id}:{test_txn_id}:payment.captured")

    print("\n✅ Verification Claim Passed: Redis state transitions enforced strictly, and 24h idempotency lock deduplicates replayed webhooks.")

if __name__ == "__main__":
    test_redis_state_and_idempotency()
