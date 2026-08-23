"""
Phase 1b Unit Test: Treatment/Control Split & Causal Mechanism Verification.

Validates:
1. Synthetic causal mechanism produces a clear, learnable Conditional Average Treatment Effect (CATE).
2. For non-self-resolvers (gt_would_self_resolve=False), treated resolution rate is substantially higher than control (~0%).
3. For self-resolvers (gt_would_self_resolve=True), control resolution rate is near ~100% (confirming 'sure things').
"""
from collections import defaultdict
from simulator.generator import generate_batch

def test_causal_mechanism_and_uplift_effect():
    batch_size = 10000
    print(f"\n--- Generating Phase 1b synthetic batch (N={batch_size}) ---")
    records = generate_batch(n=batch_size, output_path="simulator/data/test_phase1b_batch.csv")
    
    assert len(records) == batch_size, f"Expected {batch_size} records, got {len(records)}"
    
    # Bucket by (gt_would_self_resolve, is_treated)
    buckets = defaultdict(lambda: {"total": 0, "resolved": 0})
    
    for r in records:
        key = (bool(r["gt_would_self_resolve"]), bool(r["is_treated"]))
        buckets[key]["total"] += 1
        if r["actually_resolved"]:
            buckets[key]["resolved"] += 1

    print("\n======================================================================================")
    print("                 PHASE 1b CAUSAL MECHANISM & UPLIFT VERIFICATION MATRIX")
    print("======================================================================================")
    print(f"{'Self-Resolve Group (gt)':<25} | {'Treatment (is_treated)':<24} | {'Total':<7} | {'Resolved':<8} | {'Rate %':<8}")
    print("-" * 86)
    
    # 1. Non-self-resolvers (Persuadables)
    t_persuade_tot = buckets[(False, True)]["total"]
    t_persuade_res = buckets[(False, True)]["resolved"]
    t_persuade_rate = (t_persuade_res / t_persuade_tot) * 100 if t_persuade_tot else 0
    
    c_persuade_tot = buckets[(False, False)]["total"]
    c_persuade_res = buckets[(False, False)]["resolved"]
    c_persuade_rate = (c_persuade_res / c_persuade_tot) * 100 if c_persuade_tot else 0
    
    # 2. Self-resolvers (Sure things)
    t_self_tot = buckets[(True, True)]["total"]
    t_self_res = buckets[(True, True)]["resolved"]
    t_self_rate = (t_self_res / t_self_tot) * 100 if t_self_tot else 0
    
    c_self_tot = buckets[(True, False)]["total"]
    c_self_res = buckets[(True, False)]["resolved"]
    c_self_rate = (c_self_res / c_self_tot) * 100 if c_self_tot else 0
    
    print(f"{'False (Persuadables)':<25} | {'True  (Treated)':<24} | {t_persuade_tot:<7} | {t_persuade_res:<8} | {t_persuade_rate:>6.1f}%")
    print(f"{'False (Persuadables)':<25} | {'False (Control)':<24} | {c_persuade_tot:<7} | {c_persuade_res:<8} | {c_persuade_rate:>6.1f}%")
    print("-" * 86)
    print(f"{'True  (Self-Resolvers)':<25} | {'True  (Treated)':<24} | {t_self_tot:<7} | {t_self_res:<8} | {t_self_rate:>6.1f}%")
    print(f"{'True  (Self-Resolvers)':<25} | {'False (Control)':<24} | {c_self_tot:<7} | {c_self_res:<8} | {c_self_rate:>6.1f}%")
    print("-" * 86)
    
    treatment_effect = t_persuade_rate - c_persuade_rate
    print(f"\nEmpirical Treatment Effect (CATE) on Persuadables: +{treatment_effect:.1f}%")
    
    # Assertions proving learnability for Uplift T-Learner
    assert c_persuade_rate == 0.0, f"Expected 0% control resolution on non-self-resolvers, got {c_persuade_rate}%"
    assert t_persuade_rate >= 35.0, f"Expected >=35% treated resolution on non-self-resolvers, got {t_persuade_rate}%"
    assert c_self_rate >= 95.0, f"Expected >=95% control resolution on self-resolvers, got {c_self_rate}%"
    assert treatment_effect >= 35.0, f"Treatment effect too small: {treatment_effect}%"
    
    print("\n✅ Verification Claim Passed: Derived actually_resolved rate differs significantly between treated and control groups, creating a mathematically learnable causal treatment effect.")

if __name__ == "__main__":
    test_causal_mechanism_and_uplift_effect()
