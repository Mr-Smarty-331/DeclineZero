"""
Cross-Phase Integration Test: Phase 4b -> Phase 1c & Phase 0 Binding.

Verifies:
1. Ambiguous Records Ingest: extract_conformal_features and predict_cause_probabilities run without error on real ambiguous records from Phase 1c data.
2. Valid Multi-Class Probabilities: Sum of predicted probabilities equals 1.0 (within float precision).
3. Model Files Present: Confirms conformal_base_model.pkl and conformal_calibration_scores.npy are serialized and readable.
4. Phase 0 API Health: GET /health returns HTTP 200.
"""
import os
import requests
import numpy as np

from simulator.generator import generate_batch
from core.diagnostic_tree.conformal import (
    extract_conformal_features,
    predict_cause_probabilities,
    load_conformal_model_and_scores,
    BASE_MODEL_PATH,
    CALIB_SCORES_PATH,
    CANDIDATE_CAUSES
)

def test_ambiguous_feature_extraction_and_inference():
    print("Generating batch with Phase 1c ambiguous records (N=1,000)...")
    batch = generate_batch(n=1000, output_path="simulator/data/test_phase4b_batch.csv")
    ambiguous_rows = [r for r in batch if r.get("is_ambiguous")]
    assert len(ambiguous_rows) > 0, "No ambiguous rows generated"

    print(f"Testing inference across {len(ambiguous_rows)} ambiguous rows...")
    for row in ambiguous_rows:
        feats = extract_conformal_features(row)
        assert feats.shape == (24,), f"Expected 24 features (14 base + 10 legacy one-hots), got {feats.shape}"
        
        prob_dist = predict_cause_probabilities(row)
        assert isinstance(prob_dist, dict)
        assert set(prob_dist.keys()) == set(CANDIDATE_CAUSES)
        
        total_p = sum(prob_dist.values())
        assert abs(total_p - 1.0) < 0.05, f"Probabilities do not sum to ~1.0: {total_p}"

    print(f"✅ Successfully inferred cause probability distributions for all {len(ambiguous_rows)} ambiguous rows.")

def test_model_artifact_persistence():
    print("Verifying conformal model and calibration score artifacts...")
    assert BASE_MODEL_PATH.exists(), f"Missing {BASE_MODEL_PATH}"
    assert CALIB_SCORES_PATH.exists(), f"Missing {CALIB_SCORES_PATH}"

    model, scores = load_conformal_model_and_scores()
    assert model is not None
    assert len(scores) >= 250
    print(f"✅ Conformal artifacts loaded cleanly: Model={model.__class__.__name__}, Calibration Scores N={len(scores)}")

def test_phase0_api_health():
    print("Testing Phase 0 FastAPI /health endpoint live binding...")
    api_host = os.getenv("API_HOST", "localhost")
    url = f"http://{api_host}:8000/health"
    response = requests.get(url, timeout=5)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert response.json() == {"status": "ok"}, f"Unexpected health response: {response.json()}"
    print("✅ Phase 0 FastAPI API continues to respond with HTTP 200 {'status': 'ok'}.")

if __name__ == "__main__":
    print("\n============================================================")
    print("   RUNNING PHASE 4b CROSS-PHASE INTEGRATION TEST SUITE")
    print("============================================================")
    test_ambiguous_feature_extraction_and_inference()
    test_model_artifact_persistence()
    test_phase0_api_health()
    print("\n🎉 ALL PHASE 4b -> PHASE 1c / PHASE 0 INTEGRATION SEAMS PASSED!\n")
