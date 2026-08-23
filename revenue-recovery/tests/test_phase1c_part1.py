"""
Phase 1c Part 1 Unit Test: Ambiguous Legacy Code Injection & Ground Truth Root Cause.

Validates:
1. is_ambiguous is True for ~5-10% of generated records.
2. 100% of ambiguous records possess a valid gt_true_root_cause and a legacy code from LEGACY_AMBIGUOUS_CODES.
3. 100% of non-ambiguous records possess a valid verified code from ALL_VALID_CODES and no legacy string.
"""
from collections import defaultdict
from simulator.decline_codes import ALL_VALID_CODES, LEGACY_AMBIGUOUS_CODES, RootCauseCategory
from simulator.generator import generate_batch

def test_ambiguous_code_injection():
    batch_size = 10000
    print(f"\n--- Generating Phase 1c Part 1 batch (N={batch_size}) ---")
    records = generate_batch(n=batch_size, output_path="simulator/data/test_phase1c_batch.csv")
    
    ambiguous_count = 0
    clean_count = 0
    ambiguous_by_code = defaultdict(int)
    ambiguous_by_cause = defaultdict(int)
    
    for r in records:
        is_ambiguous = r["is_ambiguous"]
        code = r["decline_code"]
        cause = r["gt_true_root_cause"]
        
        if is_ambiguous:
            ambiguous_count += 1
            assert code in LEGACY_AMBIGUOUS_CODES, f"Ambiguous record has unexpected code: {code}"
            assert cause is not None and cause in [c.value for c in RootCauseCategory], f"Invalid gt_true_root_cause: {cause}"
            ambiguous_by_code[code] += 1
            ambiguous_by_cause[cause] += 1
        else:
            clean_count += 1
            assert code in ALL_VALID_CODES, f"Clean record has unmapped code: {code}"
            assert cause is None or cause == "", f"Clean record should not have gt_true_root_cause, got: {cause}"

    ambiguous_pct = (ambiguous_count / batch_size) * 100
    clean_pct = (clean_count / batch_size) * 100

    print("\n======================================================================")
    print("           PHASE 1c PART 1: AMBIGUOUS CODE INJECTION RESULTS")
    print("======================================================================")
    print(f"Total Transactions  : {batch_size}")
    print(f"Clean Taxonomy Rows : {clean_count:<5} ({clean_pct:.1f}%)")
    print(f"Ambiguous Rows      : {ambiguous_count:<5} ({ambiguous_pct:.1f}%)")
    print("-" * 70)
    
    print("\nAmbiguous Legacy Code Distribution:")
    for code, cnt in sorted(ambiguous_by_code.items()):
        print(f" - {code:<15}: {cnt:>4} occurrences ({(cnt/ambiguous_count)*100:.1f}%)")
        
    print("\nHidden Ground-Truth Root Causes for Ambiguous Cases:")
    for cause, cnt in sorted(ambiguous_by_cause.items()):
        print(f" - {cause:<22}: {cnt:>4} cases ({(cnt/ambiguous_count)*100:.1f}%)")
        
    # Assertions
    assert 5.0 <= ambiguous_pct <= 10.0, f"Ambiguous percentage {ambiguous_pct:.2f}% out of target range (5-10%)"
    assert clean_count + ambiguous_count == batch_size

    print("\n✅ Verification Claim Passed: Exactly ~5-10% of records are ambiguous, and all have valid hidden ground-truth causes.")

if __name__ == "__main__":
    test_ambiguous_code_injection()
