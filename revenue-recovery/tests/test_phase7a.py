"""
Phase 7a Unit Test: Cryptographic SHA-256 Hash Chain & Independent Verification.

Validates:
1. Sequential Log Appends: Records 10 sequential transitions with diverse fields.
2. Independent Manual Recomputation: Re-executes the SHA-256 leaf and chain hash formulas in pure Python, comparing bit-for-bit against Postgres.
3. Concurrency-safe Top-of-Chain: Confirms chain_state.running_hash equals the 10th transition's hash.
"""
import hashlib
import json
from datetime import datetime, timezone
import uuid

from core.audit_trail.merkle_log import (
    init_audit_db,
    log_transition,
    compute_leaf,
    get_current_chain_hash,
    get_db_connection,
    GENESIS_HASH
)

def test_hash_chain_sequential_integrity():
    print("\n--- Running Phase 7a Hash Chain Cryptographic Unit Tests ---")
    init_audit_db()

    # Get current tip before starting test batch
    initial_tip = get_current_chain_hash()
    print(f"Initial Chain Tip: {initial_tip[:16]}...")

    # Log 10 sequential transitions
    logged_hashes = []
    independent_hashes = []
    current_independent_hash = initial_tip

    print("\nLogging 10 Sequential State Transitions to Postgres:")
    for i in range(1, 11):
        txn_id = f"test_chain_txn_{i}_{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc)
        to_state = "action_sent" if i % 2 == 0 else "diagnosed"
        diag_raw = {"rule": f"RULE_TEST_{i}", "latency_ms": 0.05}
        action = f"ACTION_DISPATCH_{i}"
        stopping_rule = f"STOP_RULE_{i}" if i % 3 == 0 else None
        
        # 1. Log transition via function under test
        db_chain_hash = log_transition(
            txn_id=txn_id,
            from_state="triaged",
            to_state=to_state,
            diagnosis_raw=diag_raw,
            action_taken=action,
            stopping_rule_triggered=stopping_rule,
            cost_of_action=0.50,
            timestamp=now
        )
        logged_hashes.append(db_chain_hash)

        # 2. Independently compute in pure Python
        ts_iso = now.isoformat()
        diag_str = json.dumps(diag_raw, sort_keys=True)
        act_str = str(action or "NONE")
        stop_str = str(stopping_rule or "NONE")
        
        # Independent leaf hash
        manual_leaf = hashlib.sha256(f"{txn_id}|{ts_iso}|{diag_str}|{act_str}|{stop_str}".encode("utf-8")).hexdigest()
        
        # Independent chain hash: SHA256(prev_chain_hash + leaf_hash)
        manual_chain = hashlib.sha256((current_independent_hash + manual_leaf).encode("utf-8")).hexdigest()
        independent_hashes.append(manual_chain)
        current_independent_hash = manual_chain

        # Strict assertion at each step
        assert db_chain_hash == manual_chain, f"Hash mismatch at step {i}: DB={db_chain_hash} != Manual={manual_chain}"
        print(f"  [PASS] Step {i:>2}: Leaf={manual_leaf[:12]}... ──► ChainHash={db_chain_hash[:16]}... (Exact Match)")

    # 3. Confirm Postgres chain_state running_hash matches final manual tip
    final_db_tip = get_current_chain_hash()
    assert final_db_tip == current_independent_hash, f"Running hash {final_db_tip} != Independent final tip {current_independent_hash}"
    print(f"\nFinal Verified Running Tip: {final_db_tip}")
    print("✅ All 10 sequential hash links verified with independent manual SHA-256 recomputation.")

if __name__ == "__main__":
    test_hash_chain_sequential_integrity()
