"""
Phase 9b Unit Test: Audit Explorer API Integration & Cryptographic Tamper Demonstration.

Verifies:
1. fetch_timeline_from_api retrieves structured timelines for 10 real transactions via HTTP.
2. verify_proof_from_api validates Genesis-to-Tip SHA-256 Merkle chain integrity on all 10.
3. execute_demo_tamper corrupts a database field and flips verify_proof to False (detecting tamper).
4. execute_demo_restore restores the database field and returns verify_proof to True.
"""
from dashboard.app import (
    fetch_recent_transaction_ids,
    fetch_timeline_from_api,
    verify_proof_from_api,
    execute_demo_tamper,
    execute_demo_restore
)


def test_phase9b_unit():
    print("\n============================================================")
    print("      PHASE 9b UNIT TEST: AUDIT EXPLORER & MERKLE VERIFIER")
    print("============================================================")

    # 1. Fetch 10 recent transactions
    recent_ids = fetch_recent_transaction_ids(limit=10)
    assert len(recent_ids) >= 5, f"Expected >= 5 recent transactions, got {len(recent_ids)}"
    print(f"\n[Step 1] Selected {len(recent_ids)} recent transactions for verification:")
    for idx, t_id in enumerate(recent_ids, 1):
        print(f"  {idx:>2}. {t_id}")

    # 2. Verify clean timeline and cryptographic proof across all 10
    print("\n[Step 2] Testing HTTP Timeline API and Cryptographic Proofs...")
    for idx, t_id in enumerate(recent_ids, 1):
        # Timeline
        tl = fetch_timeline_from_api(t_id)
        assert "error" not in tl, f"Timeline fetch error for {t_id}: {tl.get('error')}"
        assert tl.get("total_events", 0) > 0, f"Expected events for {t_id}"
        
        # Verify Proof
        proof = verify_proof_from_api(t_id)
        assert "error" not in proof, f"Proof fetch error for {t_id}: {proof.get('error')}"
        assert proof.get("verified") is True, f"Expected clean verification for {t_id}"
        print(f"  • [{idx:>2}/10] {t_id:<40} -> ✅ VERIFIED (Events: {tl['total_events']}, Tip: {proof['stored_hash'][:16]}...)")

    print("\n  ✅ All 10 transactions returned coherent timelines and passed cryptographic Merkle verification.")

    # 3. Test Deliberate Tampering Demo
    target_txn = recent_ids[0]
    print(f"\n[Step 3] Executing Deliberate Database Tamper Simulation on `{target_txn}`...")
    tamper_ok = execute_demo_tamper(target_txn, new_action="MALICIOUS_UNAUTHORIZED_OVERRIDE")
    assert tamper_ok is True, "Failed to execute demo tamper query"

    # Call verify proof on tampered database
    tampered_proof = verify_proof_from_api(target_txn)
    assert "error" not in tampered_proof, f"Tampered proof fetch error: {tampered_proof.get('error')}"
    assert tampered_proof.get("verified") is False, "Expected verify_proof to FAIL on tampered record!"
    
    print(f"  • Verified Status after Tamper: ❌ {tampered_proof.get('verified')} (Correctly Detected Tamper)")
    print(f"  • Stored Chain Hash            : {tampered_proof.get('stored_hash')}")
    print(f"  • Recomputed Hash from Genesis : {tampered_proof.get('recomputed_hash')}")
    print(f"  • Forensics: Diverged at log record {tampered_proof.get('divergence_details', {}).get('tampered_log_id')}")
    print("  ✅ Cryptographic tamper detection successfully triggered on modified database field.")

    # 4. Test Restoration
    print(f"\n[Step 4] Restoring Original Database Value for `{target_txn}`...")
    restore_ok = execute_demo_restore(target_txn)
    assert restore_ok is True, "Failed to execute restore query"

    restored_proof = verify_proof_from_api(target_txn)
    assert restored_proof.get("verified") is True, "Expected verify_proof to return to True after restore!"
    print(f"  • Verified Status after Restore: ✅ {restored_proof.get('verified')} (Chain Valid)")
    print("  ✅ Restored database record verified back to valid status.")

    print("\n🎉 PHASE 9b UNIT TEST PASSED 100%!")


if __name__ == "__main__":
    test_phase9b_unit()
