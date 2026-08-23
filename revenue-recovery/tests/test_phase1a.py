"""
Phase 1a Verification Test: Core Decline-Code Taxonomy & Synthetic Batch Generation.
"""
from collections import defaultdict
from simulator.decline_codes import ALL_VALID_CODES, RISK_FLAGGED_CODES
from simulator.generator import generate_batch

def test_batch_generation_and_taxonomy():
    batch_size = 1000
    output_csv = "simulator/data/test_batch_1000.csv"
    
    print(f"\n--- Generating synthetic batch (N={batch_size}) ---")
    records = generate_batch(n=batch_size, output_path=output_csv)
    
    assert len(records) == batch_size, f"Expected {batch_size} records, got {len(records)}"
    
    counts_by_category = defaultdict(lambda: defaultdict(int))
    total_by_category = defaultdict(int)
    
    for r in records:
        category = r["category"]
        code = r["decline_code"]
        
        # 1. Assert decline code is non-null and strictly within taxonomy
        assert code is not None and code != "", "Encountered null or empty decline code"
        assert code in ALL_VALID_CODES, f"Encountered unknown/invented decline code: {code}"
        
        counts_by_category[category][code] += 1
        total_by_category[category] += 1

    print("\n======================================================================")
    print("      PHASE 1a SYNTHETIC DATASET DISTRIBUTION (N=1000)")
    print("======================================================================")
    print(f"{'Category':<15} | {'Decline Code':<25} | {'Count':<7} | {'Category %':<10}")
    print("-" * 68)
    
    for category, code_counts in sorted(counts_by_category.items()):
        cat_total = total_by_category[category]
        first_row = True
        for code, count in sorted(code_counts.items(), key=lambda x: -x[1]):
            pct = (count / cat_total) * 100
            cat_display = category if first_row else ""
            
            # Annotate code meaning
            annotation = ""
            if code in RISK_FLAGGED_CODES:
                annotation = " (Risk Flagged)"
            elif code == "U69":
                annotation = " (Timing Expired)"
            elif code == "Z9":
                annotation = " (Insufficient Funds)"
            elif code == "U28":
                annotation = " (Bank Glitch)"
            
            print(f"{cat_display:<15} | {code + annotation:<25} | {count:<7} | {pct:>8.1f}%")
            first_row = False
        print("-" * 68)

    print("\nSummary by Category:")
    for cat, total in sorted(total_by_category.items()):
        print(f" - {cat:<12}: {total:>4} records ({(total/batch_size)*100:.1f}%)")
    
    print("\n✅ Verification Claim Passed: All 1,000 records contain exactly 1 valid, non-null decline code strictly from the verified taxonomy.")

if __name__ == "__main__":
    test_batch_generation_and_taxonomy()
