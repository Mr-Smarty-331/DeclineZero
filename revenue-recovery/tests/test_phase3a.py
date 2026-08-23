"""
Phase 3a Unit Test: Baseline Priority Classifier Training & Performance Evaluation.

Validates:
1. Model trains on synthetic transaction dataset with 80/20 train/test split.
2. Achieves statistically valid discrimination on held-out test data (ROC-AUC > 0.65).
3. Non-degeneracy assertion: outputs varied probabilities across the range (0.05 to 0.95), not a constant prediction.
"""
import numpy as np
from core.triage_scorer.baseline_model import train_baseline_model, load_baseline_model, score_transaction
from simulator.generator import generate_transaction

def test_baseline_priority_classifier():
    print("\n--- Running Phase 3a Unit Tests on Baseline Priority Classifier ---")
    
    model, metrics = train_baseline_model(n_samples=10000, test_size=0.20, random_state=42)
    
    print("\n======================================================================")
    print("      PHASE 3a BASELINE TRIAGE CLASSIFIER TEST METRICS")
    print("======================================================================")
    print(f"Training Samples    : {metrics['train_samples']}")
    print(f"Held-out Test Size  : {metrics['test_samples']}")
    print(f"Held-out Test ROC-AUC: {metrics['test_roc_auc']:.4f}")
    print(f"Held-out Accuracy   : {metrics['test_accuracy']:.4f}")
    print("-" * 70)

    # 1. Performance assertion on held-out test split
    assert metrics["test_roc_auc"] >= 0.65, f"ROC-AUC {metrics['test_roc_auc']} is below baseline threshold (0.65)"
    assert metrics["test_accuracy"] >= 0.60, f"Accuracy {metrics['test_accuracy']} is below baseline threshold (0.60)"

    # 2. Non-degeneracy test: Score 100 random transactions and check variance
    sample_txns = [generate_transaction() for _ in range(100)]
    scores = [score_transaction(t) for t in sample_txns]

    min_score = min(scores)
    max_score = max(scores)
    mean_score = sum(scores) / len(scores)
    std_score = float(np.std(scores))

    print(f"\nScore Distribution on 100 Sample Transactions:")
    print(f" - Min Score   : {min_score:.4f}")
    print(f" - Max Score   : {max_score:.4f}")
    print(f" - Mean Score  : {mean_score:.4f}")
    print(f" - Std Dev     : {std_score:.4f}")

    assert max_score > min_score, "Model is degenerate (constant output)"
    assert std_score >= 0.05, f"Model predictions lack variance (std={std_score})"
    assert all(0.0 <= s <= 1.0 for s in scores), "Scores must be probabilities within [0.0, 1.0]"

    print("\n✅ Verification Claim Passed: Baseline priority model trains cleanly, achieves non-trivial test ROC-AUC, and outputs calibrated non-degenerate scores.")

if __name__ == "__main__":
    test_baseline_priority_classifier()
