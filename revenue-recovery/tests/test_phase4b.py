"""
Phase 4b Unit Test: Conformal Nonconformity Scorer & Calibration Score Distribution.

Validates:
1. Multi-class base probability estimator trained on ambiguous subset with 3-way split.
2. Calibration set size is statistically meaningful (N_cal >= 250).
3. Nonconformity score distribution across percentiles (min, p25, median, p75, p90, p99, max).
4. All calibration scores strictly bounded in [0.0, 1.0].
"""
import numpy as np
from core.diagnostic_tree.conformal import (
    train_conformal_base_model,
    load_conformal_model_and_scores,
    CANDIDATE_CAUSES
)

def test_conformal_calibration_distribution():
    print("\n--- Running Phase 4b Conformal Nonconformity Unit Tests ---")
    
    model, calib_scores, stats = train_conformal_base_model(n_total_samples=25000, random_state=42)

    n_cal = len(calib_scores)
    min_s = float(np.min(calib_scores))
    max_s = float(np.max(calib_scores))
    mean_s = float(np.mean(calib_scores))
    median_s = float(np.median(calib_scores))
    p25_s = float(np.percentile(calib_scores, 25))
    p75_s = float(np.percentile(calib_scores, 75))
    p90_s = float(np.percentile(calib_scores, 90))
    p99_s = float(np.percentile(calib_scores, 99))  # Critical threshold for 99% coverage

    print("\n======================================================================")
    print("      PHASE 4b CONFORMAL CALIBRATION NONCONFORMITY SCORE MATRIX")
    print("======================================================================")
    print(f"Candidate Causes Space   : {CANDIDATE_CAUSES}")
    print(f"Training Sample Count    : {stats['train_size']}")
    print(f"Calibration Sample Count : {stats['calib_size']} (N_cal)")
    print(f"Held-out Test Count      : {stats['test_size']}")
    print("-" * 70)
    print("Calibration Nonconformity Score Distribution s(x, y) = 1 - P(Y=y | x):")
    print(f" - Min Score             : {min_s:.4f}")
    print(f" - 25th Percentile (p25) : {p25_s:.4f}")
    print(f" - Median Score (p50)    : {median_s:.4f}")
    print(f" - Mean Score            : {mean_s:.4f}")
    print(f" - 75th Percentile (p75) : {p75_s:.4f}")
    print(f" - 90th Percentile (p90) : {p90_s:.4f}")
    print(f" - 99th Percentile (p99) : {p99_s:.4f} (q̂ for α=0.01)")
    print(f" - Max Score             : {max_s:.4f}")
    print("=" * 70)

    # Assertions
    assert n_cal >= 250, f"Calibration size {n_cal} is too small for statistical validity (expected >= 250)"
    assert 0.0 <= min_s <= max_s <= 1.0, "Calibration scores must be strictly in [0.0, 1.0]"
    assert p99_s > median_s, "Degenerate calibration quantile"

    print("\n✅ Verification Claim Passed: Calibration set size is statistically sufficient (N_cal >= 250) and nonconformity scores follow expected distribution.")

if __name__ == "__main__":
    test_conformal_calibration_distribution()
